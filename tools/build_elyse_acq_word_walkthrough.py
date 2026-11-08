"""Build a read-only, source-linked ELYSE Acquisition VI walkthrough."""

from pathlib import Path

from PIL import Image
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(r"C:\dev\ELYSE-ACQ-analysis")
SHOTS = ROOT / "runs" / "20260922-085500-+0200" / "images"
RENDERED = ROOT / "offline" / "rendered_png"
OUTPUT = Path(r"C:\dev\pyconlyse\docs\ELYSE_ACQ_NI6703_HT_WALKTHROUGH_2026-09-30.docx")


def set_font(style, name, size, bold=False):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(qn("w:" + attr), name)


def set_cell_shading(cell, fill):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tcpr.append(shd)


def set_cell_border(cell):
    tcpr = cell._tc.get_or_add_tcPr()
    borders = tcpr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tcpr.append(borders)
    for side in ("top", "left", "bottom", "right"):
        node = OxmlElement("w:" + side)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:color"), "D9D9D9")
        borders.append(node)


def set_cell_padding(cell, top=100, left=110, bottom=100, right=110):
    tcpr = cell._tc.get_or_add_tcPr()
    margins = tcpr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tcpr.append(margins)
    for side, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        node = OxmlElement("w:" + side)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")
        margins.append(node)


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    for i, (label, width) in enumerate(zip(headers, widths)):
        table.columns[i].width = Inches(width)
        cell = table.rows[0].cells[i]
        cell.width = Inches(width)
        cell.text = label
        set_cell_shading(cell, "E8EDF2")
        for run in cell.paragraphs[0].runs:
            run.bold = True
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_border(cell)
        set_cell_padding(cell)
    for ri, row in enumerate(rows):
        cells = table.add_row().cells
        for i, (value, width) in enumerate(zip(row, widths)):
            cells[i].width = Inches(width)
            cells[i].text = value
            if ri % 2:
                set_cell_shading(cells[i], "F7F9FB")
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_border(cells[i])
            set_cell_padding(cells[i])
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_caption(doc, number, title, filename, note=None):
    p = doc.add_paragraph(style="Caption")
    p.paragraph_format.keep_with_next = False
    p.add_run(f"Рисунок {number}. {title}. ").bold = True
    p.add_run(f"Исходный файл: {filename}.")
    if note:
        p.add_run(" " + note)
    return p


def add_crop(doc, path, box, width=6.85):
    with Image.open(path) as im:
        full_w, full_h = im.size
    x0, y0, x1, y1 = box
    assert 0 <= x0 < x1 <= full_w and 0 <= y0 < y1 <= full_h
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    shape = p.add_run().add_picture(str(path), width=Inches(width))
    shape.height = Inches(width * (y1 - y0) / (x1 - x0))
    blip_fill = shape._inline.graphic.graphicData.pic.blipFill
    src_rect = OxmlElement("a:srcRect")
    for side, value in (
        ("l", x0 / full_w),
        ("t", y0 / full_h),
        ("r", (full_w - x1) / full_w),
        ("b", (full_h - y1) / full_h),
    ):
        src_rect.set(side, str(round(value * 100000)))
    blip_fill.insert(1, src_rect)
    return p


def para(doc, text, bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        p.add_run(bold_lead).bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def heading(doc, text):
    doc.add_heading(text, level=1)


def page(doc):
    doc.add_page_break()


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Inches(8.5)
    sec.page_height = Inches(11)
    sec.top_margin = Inches(0.72)
    sec.bottom_margin = Inches(0.68)
    sec.left_margin = Inches(0.78)
    sec.right_margin = Inches(0.77)

    styles = doc.styles
    set_font(styles["Normal"], "Arial", 10.5)
    styles["Normal"].paragraph_format.space_after = Pt(6)
    styles["Normal"].paragraph_format.line_spacing = 1.13
    set_font(styles["Title"], "Arial", 17, True)
    styles["Title"].paragraph_format.space_after = Pt(10)
    set_font(styles["Heading 1"], "Arial", 13.5, True)
    styles["Heading 1"].paragraph_format.space_before = Pt(4)
    styles["Heading 1"].paragraph_format.space_after = Pt(8)
    set_font(styles["Heading 2"], "Arial", 11.5, True)
    styles["Heading 2"].paragraph_format.space_before = Pt(8)
    styles["Heading 2"].paragraph_format.space_after = Pt(5)
    set_font(styles["Caption"], "Arial", 8.5)
    styles["Caption"].paragraph_format.space_after = Pt(10)
    styles["Caption"].paragraph_format.line_spacing = 1.0

    # Page 1: graph entry and sequence scope.
    title = doc.add_paragraph("ELYSE Acquisition инициализация NI6703 и условная остановка HT", style="Title")
    title_border = OxmlElement("w:pBdr")
    title_bottom = OxmlElement("w:bottom")
    title_bottom.set(qn("w:val"), "nil")
    title_border.append(title_bottom)
    title._p.get_or_add_pPr().append(title_border)
    para(doc, "Разбор показывает путь команды HT через сохранённый 0_ACQ_ELYSE.vi: создание задачи NI6703, начальные значения C9, публикацию в PSP, вызов записи на карту, снижение команды при условной общей остановке и закрытие ссылок. Каждый переход сопоставлен с кадром диаграммы. Цель — проверить чтение проводов, а не задать порядок действий на работающей установке.")
    para(doc, "Ключевой результат: уже при инициализации логическая команда C9[0] равна 6.5, а не нулю. Функция записи масштабирует её с коэффициентом 0.5 и, если вызов доходит до DAQmx Write без ошибки, запрашивает 3.25 V на /9/ao0. Эти числа не являются измерением напряжения источника HT.")
    heading(doc, "Где начинается путь на диаграмме")
    para(doc, "Внешняя последовательность 0_ACQ_ELYSE.vi переходит к кадру 1 «Initialisation». Внутренний кадр 1[0..5] содержит четыре узла инициализации карт, соединённые жёлтым проводом кластера ошибок. Справа находится вызов 1_ACQ_INIT_NI6703.vi, а его задача возвращается в ID 4xNI6703. Положение узлов слева направо здесь дополнено проводом ошибок; без провода одно расположение не доказывало бы порядок.")
    add_crop(doc, SHOTS / "EV-ACQ-0003-init-daqmx-cards.png", (85, 205, 1245, 575), 6.9)
    add_caption(doc, 1, "Внешний кадр 1 и внутренний кадр 1 инициализации карт", "EV-ACQ-0003-init-daqmx-cards.png")
    para(doc, "Для сверки найдите в LabVIEW селекторы 1[0..4] и 1[0..5]. На жёлтом проводе последовательно стоят инициализаторы NI6602, NI6071E, DIO96 и NI6703. Этот кадр создаёт задачи; начальные команды появляются позднее, в кадре 1/5/0.")

    # Page 2: exact C9 task creation.
    page(doc)
    heading(doc, "Как создаётся задача аналоговых выходов C9")
    para(doc, "В 1_ACQ_INIT_NI6703.vi четыре внешних кадра соответствуют C6, C7, C8 и C9. На рисунке выбран четвёртый кадр 3[0..3]. Цикл For выполняет десять итераций и создаёт каналы /9/ao0 ... /9/ao9. Входы минимального и максимального напряжения узла DAQmx Create Virtual Channel получают -10 и +10 V. Ссылка задачи входит в поле C9_NI6703 общего кластера и возвращается вызывающему VI.")
    add_crop(doc, RENDERED / "1_ACQ_INIT_NI6703.png", (402, 95, 1165, 475), 6.8)
    add_caption(doc, 2, "Кадр C9 в 1_ACQ_INIT_NI6703.vi", "1_ACQ_INIT_NI6703.png", "Рендер сохранённой диаграммы из извлечённого VI; это не экранное фото XP.")
    para(doc, "Слева в полном рисунке есть таблицы Vmin C9, Vmax C9, Pente C9 и Offset C9. Они не подменяют прямые входы -10 и +10 V у DAQmx на показанном проводе. Это различие важно: диапазон задачи задаётся здесь, а масштабирование логических команд выполняется позже в 1_ACQ_WRITE_NI6703.vi.")
    para(doc, "Вывод для Python-модели: создание задачи и запись команды — разные переходы. Наличие ссылки C9_NI6703 само по себе не означает, что /9/ao0 уже получил 3.25 V.")

    # Page 3: startup vector.
    page(doc)
    heading(doc, "Какие значения задаются до первого обмена с картами")
    para(doc, "Внешний кадр 1, внутренний кадр 5, подкадр 0[0..4] записывает семь выходных банков в локальные переменные. На рисунке C9NI6703 — нижний оранжевый массив: его первый элемент 6.5. Верхний массив C8 содержит 21, 27.9 и 360 в соответствующих полях; C6 и C7 получают нули. Булевы массивы задают также начальные команды останова. Это логические значения кластеров, не показания приборов.")
    add_crop(doc, SHOTS / "EV-ACQ-0007-init-output-state-inner0.png", (245, 275, 995, 805), 6.65)
    add_caption(doc, 3, "Подкадр 1/5/0 с исходными AO и DIO банками", "EV-ACQ-0007-init-output-state-inner0.png")
    add_table(doc, ("Банк", "Ненулевые или True поля"), (
        ("C9NI6703", "[0]=6.5 HT; [2,3]=4.755; [4,5,6]=2.126"),
        ("C8NI6703", "[1]=21; [2]=27.9; [6]=360"),
        ("C3 / C4 / C5", "C3[1,4], C4[1,4,6,8,17,19], C5[33] = True"),
    ), (1.55, 5.35))
    para(doc, "Подписи некоторых констант в исходном VI скопированы от других банков. Поэтому привязка выше определяется по выходному проводу к конкретной локальной переменной и по порядку полей её типа, а не по подписи самой константы.")

    # Page 4: PSP then card writer.
    page(doc)
    heading(doc, "Как начальная команда доходит до записи на NI6703")
    para(doc, "Подкадр 1/5/1 публикует C6, C7, C8, C9 и DIO выходные банки в ni.var.psp://10.20.30.2/SUPERVISION. Следующий подкадр 1/5/2 выполняет начальный обмен: чтение NI6071E, обмен DIO96 и вызов 1_ACQ_WRITE_NI6703.vi. Последовательность подкадров задаёт порядок «локальные значения → PSP → вызов записи», а жёлтый провод ошибок связывает вызовы внутри кадра обмена.")
    add_crop(doc, SHOTS / "EV-ACQ-0008-startup-psp-output-writes.png", (185, 280, 995, 730), 6.4)
    add_caption(doc, 4, "Публикация начальных выходных банков в PSP", "EV-ACQ-0008-startup-psp-output-writes.png")
    add_crop(doc, SHOTS / "EV-ACQ-0009-startup-initial-daq-io.png", (285, 350, 1120, 670), 6.4)
    add_caption(doc, 5, "Следующий подкадр с вызовом записи NI6703", "EV-ACQ-0009-startup-initial-daq-io.png")
    para(doc, "В 1_ACQ_WRITE_NI6703.vi C9[0] умножается на 0.5. Для стартового 6.5 получается расчётный запрос 3.25 V к DAQmx Write по /9/ao0. Реальный уровень на клемме, результат DAQmx Write и напряжение самого источника HT этими рисунками не измерены.")

    # Page 5: the writer's C9 branch, needed to visually verify the scale.
    page(doc)
    heading(doc, "Где коэффициент 0.5 превращает C9 в запрос DAQmx")
    para(doc, "В 1_ACQ_WRITE_NI6703.vi четыре пути C6–C9 заканчиваются отдельными DAQmx Write. Для C9 массив Pente C9 начинается значением 0.5. Массив Valeurs_C9 умножается на Pente C9, а результат идёт в последний DAQmx Write вместе со ссылкой задачи C9_NI6703. Жёлтый провод ошибки проходит через предыдущие три записи. Число 20 на входе узла — тайм-аут вызова в секундах, а не команда напряжения.")
    add_crop(doc, RENDERED / "1_ACQ_WRITE_NI6703.png", (875, 135, 1235, 510), 5.45)
    add_caption(doc, 6, "Ветка C9 функции 1_ACQ_WRITE_NI6703.vi", "1_ACQ_WRITE_NI6703.png", "Рендер сохранённой диаграммы из извлечённого VI.")
    para(doc, "Это объясняет расчёт 6.5 × 0.5 = 3.25 V для /9/ao0 при нормальном выполнении вызова. На рисунке показан сформированный запрос на выход карты; ни напряжение на клемме, ни напряжение источника HT из него не следуют. Для остальных девяти каналов C9 используются соответствующие элементы двух массивов, а не то же значение 6.5.")

    # Page 6: conditional ramp.
    page(doc)
    heading(doc, "Как снижается команда HT в отдельной ветви остановки")
    para(doc, "Этот путь не равен обычной кнопке Arrêt HT. После выхода пяти рабочих циклов внешний кадр 3 проверяет TCP ED. При True нижний цикл проверяет Arrêt général; только его True-ветвь входит в семифазную последовательность. На рисунке показана фаза 0: локальный C9[0] сравнивается с 6.6. Если команда не меньше 6.6, из неё вычитается 0.1, новый C9[0] записывается в локальный банк, и ветвь содержит ожидание 500 ms. Если команда уже меньше 6.6, цикл выходит без нового вычитания.")
    add_crop(doc, SHOTS / "EV-ACQ-0041-emergency00-ramp-ht-to-6-5kv.png", (125, 495, 910, 942), 6.85)
    add_caption(doc, 7, "Фаза 0 общей остановки и сравнение локальной команды C9[0]", "EV-ACQ-0041-emergency00-ramp-ht-to-6-5kv.png")
    para(doc, "Проверочный пример: при C9[0]=6.6 выполняется одна запись 6.5; на следующей итерации условие «меньше 6.6» завершает цикл. Здесь сравнивается команда, а не измеренное напряжение. Отдельный цикл обмена отправляет значения на NI6703; задержка 500 ms не доказывает такой же период физических изменений. Источник True для Arrêt général в сохранённом корневом VI не установлен.")

    # Page 7: HT stop command.
    page(doc)
    heading(doc, "Как записывается команда останова источника HT")
    para(doc, "В фазе 2 той же семифазной ветви поле C4_OUT_DIO96[19] «Arrêt alimentation HT» сначала получает False; в этом же подкадре находится Wait 150 ms. Следующий подкадр записывает True, третий ждёт 1000 ms. Порядок подкадров установлен, но фактическая длительность электрического импульса не измерена: локальная запись и Wait внутри одного кадра могут выполняться параллельно, а физический DIO пишет соседний цикл.")
    add_crop(doc, SHOTS / "EV-ACQ-0036-emergency02-stop-ht-supply.png", (245, 505, 905, 815), 6.5)
    add_caption(doc, 8, "Фаза 2 общей остановки и поле C4[19] в первом подкадре", "EV-ACQ-0036-emergency02-stop-ht-supply.png")

    # Page 8: final cleanup is distinct from the stop command.
    page(doc)
    heading(doc, "Что закрывается в финальном кадре")
    para(doc, "После завершения внешнего кадра 3 кадр 4 закрывает открытые PSP-ссылки в цикле For и два соединения TPG300, затем сбрасывает локальный stop в False. В самом кадре 4 не видно DAQmx Clear Task.vi. Это не доказывает, что задачи остаются открытыми: возможное освобождение ниже по стеку и реакция драйвера здесь не проверены.")
    add_crop(doc, SHOTS / "EV-ACQ-0014-cleanup-psp-tpg300.png", (270, 250, 1040, 755), 6.5)
    add_caption(doc, 9, "Внешний кадр 4 с закрытием PSP и TPG300", "EV-ACQ-0014-cleanup-psp-tpg300.png")

    # Page 9: precise audit boundary and pointers for a LabVIEW reader.
    page(doc)
    heading(doc, "Что можно проверить непосредственно в LabVIEW")
    add_table(doc, ("Вопрос", "Найти на диаграмме", "Что следует из проводов"), (
        ("Когда появляется C9[0]=6.5?", "Внешний 1 → внутренний 5 → подкадр 0", "До PSP-публикации и до вызова записи NI6703."),
        ("Куда идёт C9[0]?", "Подкадры 1 и 2; затем 1_ACQ_WRITE_NI6703.vi", "PSP C9; масштабирование 0.5; задача /9/ao0."),
        ("Что проверяет HT ramp?", "Внешний 3 → TCP ED True → Arrêt général True → фаза 0", "Локальную команду C9[0] < 6.6, не измерение HT."),
        ("Что закрывает кадр 4?", "Внешний кадр 4", "PSP и TPG300; явного DAQmx Clear Task в нём нет."),
    ), (1.55, 2.65, 2.7))
    para(doc, "Принцип чтения: границы последовательности задают порядок между кадрами; жёлтый провод ошибок задаёт зависимость вызовов внутри кадра; два узла без провода в одном кадре не упорядочены только потому, что один нарисован левее. Статус EPS и подпись «OK» нельзя принимать за измеренный электрический результат.")
    heading(doc, "Пределы вывода")
    para(doc, "Для реального управления остаются непроверенными: совпадение сохранённого LLB с установленной версией; фактическое напряжение AO и HT; полярность DIO; обработка ошибки записи; аппаратные межблокировки; достижимость ветви Arrêt général из обычного интерфейса; освобождение DAQmx-задач и поведение после прерванной остановки. Поэтому схема описывает логику сохранённого VI, но не является инструкцией по включению или безопасной остановке установки.")
    heading(doc, "Исходные материалы")
    para(doc, "ACQUISITION.llb: C:\\dev\\ELYSE-ACQ-analysis\\source\\10.20.30.10\\ACQUISITION.llb. SHA-256: EB7C08800823D025F1B4F9E8EEA89ED9878F0CF00A02427871583B99989B2F8A.")
    para(doc, "Снимки исходного LabVIEW: C:\\dev\\ELYSE-ACQ-analysis\\runs\\20260922-085500-+0200\\images. Рисунок 2: C:\\dev\\ELYSE-ACQ-analysis\\offline\\rendered_png. В документе показаны увеличенные фрагменты; исходные PNG сохраняют полный кадр.")
    para(doc, "Сверочные материалы: ELYSE_ACQ_LIFECYCLE_LOOP_AUDIT_2026-09-28.md; ELYSE_ACQ_STARTUP_COMMAND_VECTOR_AUDIT_2026-09-29.md; ELYSE_ACQ_CONTROLLED_STOP_HT_RAMP_2026-09-30.md. Статические проверки 30.09.2026: startup 152 поля и 40 AO прогнозов — PASS; HT ramp — PASS; HT stop — PASS.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
