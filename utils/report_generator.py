"""
utils/report_generator.py

Генерация PDF-отчёта статистики просмотров для партнёра Bali.go.
Без внешних зависимостей кроме reportlab — графики рисуются
средствами самого reportlab (Drawing/Rect), шрифт лежит в utils/fonts/.

Используется в handlers/admin.py для отправки отчёта клиенту.
"""
import os
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Flowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import logging
logger = logging.getLogger(__name__)

# ── Цвета бренда ────────────────────────────────────────────────────────────
BRAND_GREEN = colors.HexColor('#2ECC71')
BRAND_DARK = colors.HexColor('#1A1A2E')
BRAND_GRAY = colors.HexColor('#F4F6F9')
BRAND_BLUE = colors.HexColor('#3498DB')
BRAND_ORANGE = colors.HexColor('#E67E22')
TEXT_DARK = colors.HexColor('#2C3E50')
TEXT_GRAY = colors.HexColor('#7F8C8D')

# ── Шрифт (грузим из utils/fonts, кладём рядом с этим файлом) ───────────────
_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')


def _register_font():
    regular = os.path.join(_FONTS_DIR, 'DejaVuSans.ttf')
    bold = os.path.join(_FONTS_DIR, 'DejaVuSans-Bold.ttf')
    try:
        if os.path.exists(regular) and os.path.exists(bold):
            pdfmetrics.registerFont(TTFont('DejaVu', regular))
            pdfmetrics.registerFont(TTFont('DejaVu-Bold', bold))
            return 'DejaVu', 'DejaVu-Bold'
    except Exception as e:
        logger.warning(f"Не удалось загрузить DejaVu шрифты: {e}")
    # fallback — может не поддерживать кириллицу, но не упадёт
    return 'Helvetica', 'Helvetica-Bold'


FONT_NORMAL, FONT_BOLD = _register_font()


# ── Простая горизонтальная диаграмма как Flowable ───────────────────────────
class BarChart(Flowable):
    """
    Простая горизонтальная столбчатая диаграмма без matplotlib.
    items: список (label, value)
    """

    def __init__(self, items: List[tuple], width: float, bar_color, max_items: int = 10):
        super().__init__()
        self.items = items[:max_items]
        self.width = width
        self.bar_color = bar_color
        self.row_h = 0.9 * cm
        self.label_w = 6.5 * cm
        self.height = max(1, len(self.items)) * self.row_h + 0.3 * cm

    def draw(self):
        if not self.items:
            return
        c = self.canv
        max_val = max((v for _, v in self.items), default=1) or 1
        bar_area_w = self.width - self.label_w - 1.5 * cm

        y = self.height - self.row_h
        for label, value in self.items:
            # Подпись слева
            c.setFont(FONT_NORMAL, 8)
            c.setFillColor(TEXT_DARK)
            text = label if len(label) <= 38 else label[:35] + '...'
            c.drawString(0, y + self.row_h * 0.35, text)

            # Полоска
            bar_w = (value / max_val) * bar_area_w if max_val else 0
            bar_w = max(bar_w, 0.15 * cm) if value > 0 else 0
            c.setFillColor(self.bar_color)
            c.roundRect(self.label_w, y + self.row_h * 0.15, bar_w, self.row_h * 0.5,
                        radius=2, stroke=0, fill=1)

            # Значение справа от полоски
            c.setFont(FONT_BOLD, 8)
            c.setFillColor(TEXT_DARK)
            c.drawString(self.label_w + bar_w + 0.2 * cm,
                         y + self.row_h * 0.35, str(value))

            y -= self.row_h


# ── Стили ────────────────────────────────────────────────────────────────────
def _make_styles():
    return {
        'title': ParagraphStyle(
            'ReportTitle', fontName=FONT_BOLD, fontSize=22,
            textColor=BRAND_DARK, alignment=TA_CENTER, spaceAfter=8,
        ),
        'subtitle': ParagraphStyle(
            'ReportSubtitle', fontName=FONT_NORMAL, fontSize=11,
            textColor=TEXT_GRAY, alignment=TA_CENTER, spaceAfter=2,
        ),
        'section': ParagraphStyle(
            'Section', fontName=FONT_BOLD, fontSize=13,
            textColor=BRAND_DARK, spaceBefore=14, spaceAfter=6,
        ),
        'normal': ParagraphStyle(
            'Normal2', fontName=FONT_NORMAL, fontSize=10,
            textColor=TEXT_DARK, spaceAfter=4,
        ),
        'small': ParagraphStyle(
            'Small', fontName=FONT_NORMAL, fontSize=8,
            textColor=TEXT_GRAY, spaceAfter=2,
        ),
        'footer': ParagraphStyle(
            'Footer', fontName=FONT_NORMAL, fontSize=8,
            textColor=TEXT_GRAY, alignment=TA_CENTER,
        ),
    }


# ── KPI-блок ──────────────────────────────────────────────────────────────────
def _kpi_table(stats: Dict, styles: Dict, page_w: float):
    data = [
        [
            Paragraph(f"<b>{stats.get('total', 0)}</b>", ParagraphStyle(
                'KV', fontName=FONT_BOLD, fontSize=20, textColor=BRAND_GREEN, alignment=TA_CENTER)),
            Paragraph(f"<b>{stats.get('promotions_total', 0)}</b>", ParagraphStyle(
                'KV2', fontName=FONT_BOLD, fontSize=20, textColor=BRAND_BLUE, alignment=TA_CENTER)),
            Paragraph(f"<b>{stats.get('events_total', 0)}</b>", ParagraphStyle(
                'KV3', fontName=FONT_BOLD, fontSize=20, textColor=BRAND_ORANGE, alignment=TA_CENTER)),
            Paragraph(f"<b>{stats.get('unique_users', 0)}</b>", ParagraphStyle(
                'KV4', fontName=FONT_BOLD, fontSize=20, textColor=colors.HexColor('#9B59B6'), alignment=TA_CENTER)),
        ],
        [
            Paragraph("Всего просмотров", styles['small']),
            Paragraph("Просмотров акций", styles['small']),
            Paragraph("Просмотров событий", styles['small']),
            Paragraph("Уникальных польз.", styles['small']),
        ],
    ]
    col_w = page_w / 4
    t = Table(data, colWidths=[col_w]*4, rowHeights=[30, 16])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_GRAY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEAFTER', (0, 0), (2, -1), 0.5, colors.white),
    ]))
    return t


# ── Таблица акций/событий ────────────────────────────────────────────────────
def _items_table(items: List[Dict], label: str, styles: Dict, page_w: float):
    if not items:
        return Paragraph(f"Нет данных по {label.lower()}.", styles['small'])

    header = [
        Paragraph('№', ParagraphStyle('TH', fontName=FONT_BOLD, fontSize=9,
                                      textColor=colors.white, alignment=TA_CENTER)),
        Paragraph('Название', ParagraphStyle('TH2', fontName=FONT_BOLD, fontSize=9,
                                             textColor=colors.white)),
        Paragraph('Просмотры', ParagraphStyle('TH3', fontName=FONT_BOLD, fontSize=9,
                                              textColor=colors.white, alignment=TA_CENTER)),
    ]
    rows = [header]
    for i, item in enumerate(items, 1):
        title = item.get(
            'title') or f'{label} #{item.get("promotion_id") or item.get("event_id")}'
        views = item.get('views', 0)
        rows.append([
            Paragraph(str(i), ParagraphStyle('TD', fontName=FONT_NORMAL, fontSize=9,
                                             alignment=TA_CENTER)),
            Paragraph(str(title)[:60], ParagraphStyle(
                'TD2', fontName=FONT_NORMAL, fontSize=9)),
            Paragraph(str(views), ParagraphStyle('TD3', fontName=FONT_NORMAL, fontSize=9,
                                                 alignment=TA_CENTER)),
        ])

    t = Table(rows, colWidths=[1.2*cm, page_w - 4.2*cm, 3*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_DARK),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_GRAY]),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NORMAL),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#E0E0E0')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, BRAND_GREEN),
    ]))
    return t


# ── Основная функция ─────────────────────────────────────────────────────────
async def generate_partner_report(
    partner_name: str,
    stats: Dict,
    promotions_detail: List[Dict],
    events_detail: List[Dict],
) -> Optional[str]:
    """
    Генерирует PDF-отчёт и возвращает путь к файлу.
    Файл нужно удалить после отправки: os.unlink(path)

    Args:
        partner_name:       Название партнёра.
        stats:              Результат get_promotion_views_stats().
        promotions_detail:  Список словарей {title, views, promotion_id}.
        events_detail:      Список словарей {title, views, event_id}.

    Returns:
        Путь к временному PDF-файлу или None при ошибке.
    """
    try:
        styles = _make_styles()
        tmp_pdf = tempfile.NamedTemporaryFile(
            delete=False, suffix='.pdf', prefix='bali_go_stats_'
        )
        pdf_path = tmp_pdf.name
        tmp_pdf.close()

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        page_w = A4[0] - 4*cm

        story = []
        now = datetime.now().strftime('%d.%m.%Y %H:%M')

        # ── Шапка ──
        story.append(Paragraph("Bali.go", styles['title']))
        story.append(Paragraph("Отчёт по просмотрам", styles['subtitle']))
        story.append(Spacer(1, 0.2*cm))
        story.append(HRFlowable(width="100%", thickness=2,
                     color=BRAND_GREEN, spaceAfter=8))

        story.append(
            Paragraph(f"Партнёр: <b>{partner_name}</b>", styles['normal']))
        story.append(Paragraph(f"Дата формирования: {now}", styles['small']))
        story.append(Spacer(1, 0.4*cm))

        # ── KPI ──
        story.append(Paragraph("Общая статистика", styles['section']))
        story.append(_kpi_table(stats, styles, page_w))
        story.append(Spacer(1, 0.5*cm))

        # ── Акции ──
        story.append(HRFlowable(width="100%", thickness=0.5,
                     color=colors.HexColor('#E0E0E0')))
        story.append(
            Paragraph("Спец. предложения / Коллаборации", styles['section']))

        if promotions_detail:
            story.append(_items_table(
                promotions_detail, "Акция", styles, page_w))
            story.append(Spacer(1, 0.4*cm))
            chart_items = [
                (p.get('title') or f'Акция #{p["promotion_id"]}', p['views'])
                for p in promotions_detail
            ]
            story.append(
                BarChart(chart_items, width=page_w, bar_color=BRAND_BLUE))
        else:
            story.append(Paragraph("Акций пока нет.", styles['small']))

        story.append(Spacer(1, 0.5*cm))

        # ── События ──
        story.append(HRFlowable(width="100%", thickness=0.5,
                     color=colors.HexColor('#E0E0E0')))
        story.append(Paragraph("События", styles['section']))

        if events_detail:
            story.append(_items_table(
                events_detail, "Событие", styles, page_w))
            story.append(Spacer(1, 0.4*cm))
            chart_items = [
                (e.get('title') or f'Событие #{e["event_id"]}', e['views'])
                for e in events_detail
            ]
            story.append(
                BarChart(chart_items, width=page_w, bar_color=BRAND_ORANGE))
        else:
            story.append(Paragraph("Событий пока нет.", styles['small']))

        story.append(Spacer(1, 1*cm))

        # ── Футер ──
        story.append(HRFlowable(width="100%", thickness=0.5,
                     color=colors.HexColor('#E0E0E0')))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            f"Сформировано автоматически · Bali.go · {now}",
            styles['footer']
        ))

        doc.build(story)
        logger.info(f"PDF-отчёт сформирован: {pdf_path}")
        return pdf_path

    except Exception as e:
        logger.error(f"Ошибка генерации PDF-отчёта для {partner_name}: {e}")
        return None
