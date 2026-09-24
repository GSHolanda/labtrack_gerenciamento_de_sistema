"""PDF do relatório da amostra (ReportLab).

Adaptador de saída: recebe o relatório já montado (``SampleReport``) e só cuida da
diagramação. Trocar a biblioteca de PDF não muda o conteúdo nem as regras.

Usa a Helvetica embutida no leitor de PDF (codificação WinAnsi): nenhum arquivo de
fonte a distribuir, no Linux, no Windows ou no Docker. Caracteres fora dessa
codificação são trocados por equivalentes (``≤`` → ``<=``) ou por ``?``; o JSON do
relatório preserva o texto original.
"""

from collections.abc import Callable
from datetime import datetime
from functools import partial
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.enums import ResultSource, SampleStatus, SpecStatus
from app.domain.report import EMPTY, format_decimal, format_moment, format_spec
from app.schemas.reports import ReportResult, ReportTest, SampleReport

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 16 * mm
MARGIN_TOP = 27 * mm
MARGIN_BOTTOM = 24 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X

INK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")
BORDER = colors.HexColor("#e2e8f0")
HEADER_FILL = colors.HexColor("#f1f5f9")
SUCCESS = colors.HexColor("#15803d")
SUCCESS_FILL = colors.HexColor("#dcfce7")
DANGER_HEX = "#b91c1c"
DANGER = colors.HexColor(DANGER_HEX)
DANGER_FILL = colors.HexColor("#fef2f2")
DANGER_BORDER = colors.HexColor("#fecaca")

ORIGIN = {
    "PRODUCTION": "Produção",
    "RAW_MATERIAL": "Matéria-prima",
    "STABILITY": "Estabilidade",
    "CUSTOMER": "Cliente",
    "ENVIRONMENTAL": "Monitoramento ambiental",
}
PRIORITY = {"URGENT": "Urgente", "HIGH": "Alta", "NORMAL": "Normal", "LOW": "Baixa"}
DECISION = {SampleStatus.APPROVED: "APROVADA", SampleStatus.REJECTED: "REPROVADA"}

Moment = Callable[[datetime | None], str]
# Símbolos comuns fora da WinAnsi (o sinal de menos é U+2212).
_REPLACEMENTS = {"≤": "<=", "≥": ">=", "\u2212": "-", "→": "->", "←": "<-", "≠": "!="}


def _style(name: str, **overrides: object) -> ParagraphStyle:
    base: dict[str, object] = {
        "fontName": "Helvetica",
        "fontSize": 8.5,
        "leading": 11,
        "textColor": INK,
    }
    return ParagraphStyle(name, **{**base, **overrides})


TITLE = _style("title", fontName="Helvetica-Bold", fontSize=17, leading=21)
SUBTITLE = _style("subtitle", fontSize=10.5, leading=14, textColor=MUTED)
HEADING = _style(
    "heading", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=12, spaceAfter=5
)
BODY = _style("body")
BOLD = _style("bold", fontName="Helvetica-Bold")
LABEL = _style("label", fontSize=7.5, leading=10, textColor=MUTED)
SMALL = _style("small", fontSize=7.5, leading=10, textColor=MUTED)
NOTE = _style("note", fontSize=7.5, leading=10.5, textColor=MUTED)
BADGE = _style("badge", fontName="Helvetica-Bold", fontSize=12, leading=15, alignment=1)
BADGE_NOTE = _style("badge-note", fontSize=7.5, leading=10, textColor=MUTED, alignment=1)


def pdf_text(value: object) -> str:
    """Texto seguro para Paragraph: codificação WinAnsi e marcação escapada."""
    text = "".join(_REPLACEMENTS.get(char, char) for char in str(value))
    return escape(text.encode("cp1252", errors="replace").decode("cp1252"))


def _p(value: object, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(pdf_text(value), style)


def _rich(markup: str, style: ParagraphStyle = BODY) -> Paragraph:
    """Paragraph com marcação própria (os trechos variáveis já passaram por pdf_text)."""
    return Paragraph(markup, style)


def render_sample_report(report: SampleReport, *, emission_id: int | None = None) -> bytes:
    """Gera o PDF. ``emission_id`` é o registro REPORT_GENERATED no audit trail."""
    moment = partial(format_moment, zone=ZoneInfo(report.timezone))
    buffer = BytesIO()
    document = BaseDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Relatório de análise {report.sample.sample_code}",
        author=report.lab_name,
        subject="Relatório de análise de amostra",
        creator="LabTrack",
    )
    # Quadro sem recuo interno: títulos e tabelas alinhados à margem.
    body = Frame(
        MARGIN_X,
        MARGIN_BOTTOM,
        CONTENT_WIDTH,
        PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    page = _PageFrame(report, moment, emission_id)
    document.addPageTemplates([PageTemplate(id="report", frames=[body], onPage=page.draw)])
    document.build(_story(report, moment, emission_id), canvasmaker=_NumberedCanvas)
    return buffer.getvalue()


# --- Conteúdo ------------------------------------------------------------------------


def _story(report: SampleReport, moment: Moment, emission_id: int | None) -> list[Flowable]:
    story: list[Flowable] = [_title(report, moment), Spacer(0, 4 * mm)]
    story += [_p("Identificação da amostra", HEADING), _identification(report, moment)]

    reported = [test for test in report.tests if test.status != "CANCELLED"]
    story += [_p("Resultados", HEADING), _results(reported, moment)]

    corrected = [test for test in report.tests if test.previous_versions]
    if corrected:
        story += [
            _p("Correções de resultados", HEADING),
            _p(
                "Toda correção gera uma nova versão com justificativa; as versões anteriores "
                "continuam registradas, inclusive as que ficaram fora da especificação.",
                NOTE,
            ),
            Spacer(0, 2 * mm),
            _corrections(corrected, moment),
        ]

    cancelled = [test for test in report.tests if test.status == "CANCELLED"]
    if cancelled:
        story += [_p("Testes cancelados", HEADING), _cancellations(cancelled, moment)]

    # O parecer e as notas finais não se separam entre páginas.
    story.append(
        KeepTogether(
            [
                _p("Parecer da revisão", HEADING),
                _decision(report, moment),
                Spacer(0, 5 * mm),
                _closing_note(report, emission_id),
            ]
        )
    )
    return story


def _title(report: SampleReport, moment: Moment) -> Table:
    sample = report.sample
    approved = report.decision.status == SampleStatus.APPROVED
    tone, fill = (SUCCESS, SUCCESS_FILL) if approved else (DANGER, DANGER_FILL)
    badge = Table(
        [
            [
                _p(
                    DECISION.get(report.decision.status, report.decision.status),
                    ParagraphStyle("badge-tone", parent=BADGE, textColor=tone),
                )
            ],
            [_p(f"em {moment(report.decision.reviewed_at)}", BADGE_NOTE)],
        ],
        colWidths=[46 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill),
                ("BOX", (0, 0), (-1, -1), 1, tone),
                ("TEXTCOLOR", (0, 0), (0, 0), tone),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        ),
    )
    heading = [
        _p("Relatório de análise", TITLE),
        _p(
            f"Amostra {sample.sample_code} · {sample.product.name} · lote {sample.lot_number}",
            SUBTITLE,
        ),
    ]
    return Table(
        [[heading, badge]],
        colWidths=[CONTENT_WIDTH - 50 * mm, 50 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )


def _key_values(
    pairs: list[tuple[str, str]], *, columns: int = 2, label_width: float = 32 * mm
) -> Table:
    """Grade rótulo/valor em ``columns`` colunas; um par sozinho na linha ocupa a largura."""
    value_width = CONTENT_WIDTH / columns - label_width
    rows: list[list[Paragraph | str]] = []
    spans: list[tuple] = []
    for start in range(0, len(pairs), columns):
        row: list[Paragraph | str] = []
        for label, value in pairs[start : start + columns]:
            row += [_p(label, LABEL), _p(value)]
        if len(row) < 2 * columns:
            spans.append(("SPAN", (len(row) - 1, len(rows)), (-1, len(rows))))
            row += [""] * (2 * columns - len(row))
        rows.append(row)
    return Table(
        rows,
        colWidths=[label_width, value_width] * columns,
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                *spans,
            ]
        ),
    )


def _identification(report: SampleReport, moment: Moment) -> Flowable:
    sample = report.sample
    pairs = [
        ("Cliente", f"{sample.client.name} ({sample.client.code})"),
        ("Produto", f"{sample.product.name} ({sample.product.code})"),
        ("Lote", sample.lot_number),
        ("Origem", ORIGIN.get(sample.origin, sample.origin)),
        ("Recebida em", moment(sample.received_at)),
        ("Prioridade", PRIORITY.get(sample.priority, sample.priority)),
        ("Registrada por", sample.registered_by.full_name),
        (
            "Analista responsável",
            sample.responsible.full_name if sample.responsible else EMPTY,
        ),
        ("Enviada para revisão", moment(sample.submitted_at)),
        ("Categoria do produto", sample.product.category or EMPTY),
    ]
    if sample.notes:
        pairs.append(("Observações", sample.notes))
    return _key_values(pairs)


def _data_table(
    header: list[str], rows: list[list[Paragraph]], widths: list[float], extra: list[tuple]
) -> Table:
    table = Table(
        [[_p(title, LABEL) for title in header], *rows],
        colWidths=widths,
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                *extra,
            ]
        )
    )
    return table


def _measurement(result: ReportResult | None, test: ReportTest) -> str:
    if result is None:
        return EMPTY
    return f"{format_decimal(result.value, test.decimal_places)} {result.unit}"


def _spec_status(status: str) -> Paragraph:
    if status == SpecStatus.OOS:
        return _rich(f'<font color="{DANGER_HEX}"><b>Fora da especificação</b></font>')
    return _p("Conforme")


def _recorded_by(result: ReportResult, moment: Moment) -> Paragraph:
    who = (
        f"Equipamento {result.instrument_code}"
        if result.source == ResultSource.INSTRUMENT
        else (result.entered_by.full_name if result.entered_by else EMPTY)
    )
    return _rich(f"{pdf_text(who)}<br/>{_small(moment(result.entered_at))}")


def _small(text: str) -> str:
    return f'<font size="7.5" color="#64748b">{pdf_text(text)}</font>'


def _results(tests: list[ReportTest], moment: Moment) -> Flowable:
    if not tests:
        return _p("Nenhum teste com resultado.", NOTE)
    rows: list[list[Paragraph]] = []
    extra: list[tuple] = []
    for index, test in enumerate(tests, start=1):
        result = test.result
        value = f"<b>{pdf_text(_measurement(result, test))}</b>"
        if result is not None and result.version > 1:
            value += "<br/>" + _small(f"corrigido (versão {result.version})")
        rows.append(
            [
                _rich(
                    f"<b>{pdf_text(test.test_name)}</b><br/>"
                    + _small(f"{test.test_code} · {test.method}")
                ),
                _rich(value),
                _p(format_spec(test.spec_min, test.spec_max, test.unit, test.decimal_places)),
                _spec_status(result.spec_status) if result else _p(EMPTY),
                _recorded_by(result, moment) if result else _p(EMPTY),
            ]
        )
        if result is not None and result.spec_status == SpecStatus.OOS:
            extra.append(("BACKGROUND", (0, index), (-1, index), DANGER_FILL))
    return _data_table(
        ["Teste e método", "Resultado", "Especificação", "Situação", "Registro"],
        rows,
        [52 * mm, 28 * mm, 33 * mm, 35 * mm, CONTENT_WIDTH - 148 * mm],
        extra,
    )


def _corrections(tests: list[ReportTest], moment: Moment) -> Flowable:
    rows: list[list[Paragraph]] = []
    for test in tests:
        versions = [*test.previous_versions, *([test.result] if test.result else [])]
        for result in versions:
            label = f"v{result.version}" + (" (vigente)" if result is test.result else "")
            rows.append(
                [
                    _p(test.test_code, BOLD),
                    _p(label),
                    _p(_measurement(result, test)),
                    _spec_status(result.spec_status),
                    _recorded_by(result, moment),
                    _p(result.change_reason or EMPTY),
                ]
            )
    return _data_table(
        ["Teste", "Versão", "Valor", "Situação", "Registro", "Justificativa da correção"],
        rows,
        [22 * mm, 20 * mm, 24 * mm, 35 * mm, 34 * mm, CONTENT_WIDTH - 135 * mm],
        [],
    )


def _cancellations(tests: list[ReportTest], moment: Moment) -> Flowable:
    rows = [
        [
            _rich(f"<b>{pdf_text(test.test_name)}</b><br/>{_small(test.test_code)}"),
            _p(test.cancellation.cancelled_by if test.cancellation else EMPTY),
            _p(moment(test.cancellation.cancelled_at) if test.cancellation else EMPTY),
            _p((test.cancellation.reason if test.cancellation else None) or EMPTY),
        ]
        for test in tests
    ]
    return _data_table(
        ["Teste", "Cancelado por", "Em", "Justificativa"],
        rows,
        [48 * mm, 38 * mm, 28 * mm, CONTENT_WIDTH - 114 * mm],
        [],
    )


def _decision(report: SampleReport, moment: Moment) -> Flowable:
    decision = report.decision
    approved = decision.status == SampleStatus.APPROVED
    performers = [user.full_name for user in report.analysts]
    performers += [f"equipamento {code}" for code in report.instruments]
    pairs = [
        ("Decisão", "Aprovada" if approved else "Reprovada"),
        ("Revisor", decision.reviewed_by.full_name),
        ("Data da decisão", moment(decision.reviewed_at)),
        ("Resultados lançados por", ", ".join(performers) or EMPTY),
        (
            "Comentário da revisão" if approved else "Justificativa da reprovação",
            decision.comment or EMPTY,
        ),
    ]
    note = (
        "Aprovação confirmada com a senha do revisor, que não lançou resultados desta amostra, "
        "e sem resultado vigente fora da especificação."
        if approved
        else "Reprovação registrada pelo revisor com justificativa."
    )
    return Table(
        [[_key_values(pairs, columns=1, label_width=42 * mm)], [_p(note, NOTE)]],
        colWidths=[CONTENT_WIDTH],
        style=TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 1), (-1, 1), 4),
            ]
        ),
    )


def _closing_note(report: SampleReport, emission_id: int | None) -> Flowable:
    emission = (
        f"A emissão nº {emission_id} está registrada no audit trail com a impressão digital "
        "SHA-256 do rodapé; emissões da mesma amostra têm a mesma impressão digital."
        if emission_id is not None
        else "Prévia sem registro de emissão."
    )
    return _p(
        "Os resultados referem-se exclusivamente à amostra analisada. Limites de "
        "especificação vigentes quando os testes foram atribuídos à amostra; datas e horários "
        f"no fuso {report.timezone}. Documento emitido pelo LabTrack. {emission}",
        NOTE,
    )


# --- Cabeçalho, rodapé e numeração ----------------------------------------------------


class _PageFrame:
    """Cabeçalho e rodapé repetidos em todas as páginas."""

    def __init__(self, report: SampleReport, moment: Moment, emission_id: int | None) -> None:
        self.report = report
        self.moment = moment
        self.emission_id = emission_id

    def draw(self, canvas: Canvas, _document: BaseDocTemplate) -> None:
        report = self.report
        canvas.saveState()
        top = PAGE_HEIGHT - 14 * mm
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(MARGIN_X, top, "LabTrack")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_X, top - 11, _plain(report.lab_name))
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(PAGE_WIDTH - MARGIN_X, top, "Relatório de análise")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PAGE_WIDTH - MARGIN_X, top - 11, report.sample.sample_code)
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.75)
        canvas.line(MARGIN_X, top - 17, PAGE_WIDTH - MARGIN_X, top - 17)

        bottom = 12 * mm
        canvas.line(MARGIN_X, bottom + 14, PAGE_WIDTH - MARGIN_X, bottom + 14)
        canvas.setFont("Helvetica", 7.5)
        emitted = (
            f"Emitido em {self.moment(report.generated_at)} ({report.timezone}) "
            f"por {report.generated_by.full_name}"
        )
        if self.emission_id is not None:
            emitted += f" · emissão nº {self.emission_id}"
        canvas.drawString(MARGIN_X, bottom + 4, _plain(emitted))
        canvas.drawString(MARGIN_X, bottom - 6, f"SHA-256 {report.content_hash}")
        canvas.restoreState()


class _NumberedCanvas(Canvas):
    """Canvas que conhece o total de páginas ("Página 2 de 3") ao salvar."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self._saved_pages: list[dict[str, object]] = []

    def showPage(self) -> None:  # noqa: N802 (API do ReportLab)
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self.saveState()
            self.setFont("Helvetica", 7.5)
            self.setFillColor(MUTED)
            self.drawRightString(
                PAGE_WIDTH - MARGIN_X, 12 * mm + 4, f"Página {self._pageNumber} de {total}"
            )
            self.restoreState()
            super().showPage()
        super().save()


def _plain(text: str) -> str:
    """Texto direto no canvas (sem marcação): só a troca de caracteres."""
    value = "".join(_REPLACEMENTS.get(char, char) for char in text)
    return value.encode("cp1252", errors="replace").decode("cp1252")
