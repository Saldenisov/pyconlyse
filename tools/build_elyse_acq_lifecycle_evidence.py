"""Build a source-linked lifecycle review; never executes VI, NI, or PSP code.

Every figure embeds the original screenshot. OOXML cropping selects a region
without repainting any wire, annotation, or value. Coverage is intentionally
separate from completeness of native screenshots and from hardware behavior.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from build_elyse_acq_word_walkthrough import add_crop, add_table, para, set_font


REPO = Path(r"C:\dev\pyconlyse")
ROOT = Path(r"C:\dev\ELYSE-ACQ-analysis")
OLD = ROOT / "runs/20260922-085500-+0200/images"
NEW = ROOT / "runs/20261001-lifecycle-proof/images"
MEMBERS = ROOT / "offline/extracted/ACQUISITION_VIs_verified"
ARCHIVED_MEMBERS = ROOT / "offline/extracted/ACQUISITION_VIs"
OUTPUT = REPO / "docs/ELYSE_ACQ_INITIALIZATION_SHUTDOWN_EVIDENCE_2026-10-01.docx"
LEDGER = REPO / "docs/ELYSE_ACQ_LIFECYCLE_FIGURE_LEDGER_2026-10-01.csv"
REPORT = REPO / "docs/ELYSE_ACQ_LIFECYCLE_EVIDENCE_CHECK_2026-10-01.json"
SOURCE_SHA = "eb7c08800823d025f1b4f9e8eea89ed9878f0cf00a02427871583b99989b2f8a"

# Manually read from the eight native screenshots, not from the in-VI table.
COUNTERS = (
    (0, 31, 20, 34, "rising", True, "Synchro PCI6071E"),
    (1, 200, 3620000, 34, "rising", True, "Synchro variable MACHINE"),
    (2, 43558, 200, 30, "rising", True, "Synchro mesure WCM"),
    (3, 43658, 60, 34, "rising", False, "Synchro MODULATEUR"),
    (4, 43500, 60, 30, "rising", False, "Synchro HF"),
    (5, 101600, 2000, 30, "rising", True, "Synchro CIBLE DE FARADAY"),
    (6, 43500, 56, 30, "rising", True, "Synchro OSCILLOSCOPE"),
    (7, 20, 100000, 10, "falling", True, "Gate secteur 50 Hz"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_assets() -> dict:
    manifest = json.loads((MEMBERS / "extraction_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_sha256"] == SOURCE_SHA
    assert sha(Path(manifest["source"])) == SOURCE_SHA
    checks = {m["name"]: sha(ARCHIVED_MEMBERS / m["name"]) == m["sha256"] for m in manifest["members"]}
    assert len(checks) == 17 and all(checks.values())
    working_checks = {m["name"]: sha(MEMBERS / m["name"]) == m["sha256"] for m in manifest["members"]}
    drift = {m["name"]: {"expected_sha256": m["sha256"], "actual_sha256": sha(MEMBERS / m["name"])}
             for m in manifest["members"] if not working_checks[m["name"]]}
    with (REPO / "legacy/xp_acq_agent/data/ni6602_timing.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 8
    for row, (n, low, high, trigger, edge, started, _meaning) in zip(rows, COUNTERS):
        assert int(row["output"]) == n
        assert (int(row["low_ticks"]), int(row["high_ticks"])) == (low, high)
        assert row["trigger"] == f"/10/PFI{trigger}"
        assert row["physical_channel"] == f"/10/ctr{n}"
        assert row["timebase"] == "/10/PFI11" and int(row["initial_delay_ticks"]) == 0
        assert row["trigger_edge"] == edge and (row["started_on_init"] == "True") == started
    expected = [*(f"INIT-NI6602-frame{i}.png" for i in range(8)),
                *(f"INIT-NI6071E-frame{i}{suffix}.png" for i, suffix in ((0, ""), (1, "-C1"), (2, "-C2"))),
                "INIT-DIO96-six-tasks.png", "INIT-NI6220-full.png",
                *(f"INIT-NI6703-frame{i}-C{i+6}.png" for i in range(4))]
    assert len(expected) == 17 and all((NEW / name).is_file() for name in expected)
    return {"source_sha256": SOURCE_SHA, "member_hash_checks": checks,
            "member_hash_check_directory": str(ARCHIVED_MEMBERS),
            "working_member_hash_checks": working_checks, "working_member_drift": drift,
            "native_initialization_captures": len(expected),
            "counter_csv_rows_matched_to_manual_native_transcription": 8,
            "no_hardware_code_imported": True,
            "claim_limit": "Asset identity and transcription checks, not automatic wire recognition or live execution."}


def build():
    report = validate_assets()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin, sec.bottom_margin = Inches(.65), Inches(.65)
    sec.left_margin, sec.right_margin = Inches(.8), Inches(.8)
    for name, size, bold in (("Normal", 11, False), ("Title", 18, True),
                             ("Heading 1", 14, True), ("Heading 2", 12, True), ("Caption", 8.5, False)):
        set_font(doc.styles[name], "Arial", size, bold)
    doc.styles["Normal"].paragraph_format.space_after = Pt(7)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.08
    doc.styles["Caption"].paragraph_format.space_after = Pt(7)
    doc.styles["Caption"].paragraph_format.line_spacing = 1
    for name in ("Heading 1", "Heading 2"):
        doc.styles[name].paragraph_format.space_before = Pt(4)
        doc.styles[name].paragraph_format.space_after = Pt(7)
    footer = sec.footer.paragraphs[0]
    footer.alignment = 2
    run = footer.add_run("ELYSE Acquisition  |  ")
    run.font.size = Pt(8)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    figures = []
    page_no = 1

    def page(title):
        nonlocal page_no
        doc.add_page_break()
        page_no += 1
        doc.add_heading(title, 1)

    def shot(path, scope, box, width=6.8, coverage="native visible frame"):
        add_crop(doc, path, box, width)
        number = len(figures) + 1
        cap = doc.add_paragraph(style="Caption")
        cap.add_run(f"Рисунок {number}. {scope}. ").bold = True
        cap.add_run(path.name)
        figures.append({"figure": number, "planned_page": page_no, "scope": scope,
                        "path": str(path), "sha256": sha(path), "coverage": coverage,
                        "crop": ",".join(map(str, box))})

    def table(headers, rows, widths):
        out = add_table(doc, headers, rows, widths)
        repeat = OxmlElement("w:tblHeader")
        out.rows[0]._tr.get_or_add_trPr().append(repeat)
        for row in out.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.space_after = Pt(2)
                    for r in p.runs:
                        r.font.size = Pt(9.5)
        return out

    title = doc.add_paragraph("ELYSE Acquisition инициализация карт и проверка остановки", style="Title")
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "nil")
    borders.append(bottom)
    title._p.get_or_add_pPr().append(borders)
    para(doc, "Документ связывает действия сохранённого Acquisition с кадрами LabVIEW: создание задач всех 11 карт, выбор триггеров, начальные команды, первый обмен с картами, условную семифазную остановку и закрытие ссылок. Он предназначен для проверки чтения диаграмм перед переносом управляющей логики в Python.")
    para(doc, "Инициализация не означает обнуление оборудования. Она создаёт 21 задачу DAQmx, запускает шесть из восьми задач счётчиков и позднее вызывает запись начальных AO и DO. Остановка также не равна универсальному обнулению: её вход условный, а отдельные поля команд сохраняются.")
    table(("Карты", "Задачи", "Каналы"), (
        ("C1 и C2 NI6071E", "2 AI", "64 + 64"),
        ("C3 C4 C5 DIO96", "3 DI + 3 DO", "176 DI + 112 DO"),
        ("C6 C7 C8 C9 NI6703", "4 AO", "40 AO"),
        ("C10 NI6602", "8 CO", "8 счётчиков"),
        ("C11 NI6220", "1 AI", "16 AI"),
    ), (2.5, 1.4, 2.9))
    para(doc, "Нативные снимки создания задач охватывают все 17 видимых кадров пяти инициализаторов. Для главного VI использованы ранее сохранённые снимки. В остановке показаны все семь фаз, но не каждый вложенный кадр имеет отдельный снимок. Точный недостающий набор указан в конце; утверждение о полном покадровом подтверждении пока не сделано.")
    para(doc, "Граница вывода: параметры, провода, последовательности и присваивания сохранённого кода. Результат аппаратной записи, физический уровень напряжения и аварийная защита установки не устанавливаются этими рисунками.")

    page("Источники и способ проверки")
    para(doc, "Основной источник — копия ACQUISITION.llb объёмом 1 359 540 байт. SHA256 проверен повторно; все 17 VI в архивной папке ACQUISITION_VIs совпадают с манифестом. Открытие в 32-битной LabVIEW 2020 помечает конвертированный VI звёздочкой. Сохранение и запуск в этой проверке не выполнялись.")
    para(doc, str(ROOT / "source/10.20.30.10/ACQUISITION.llb"))
    p = para(doc, SOURCE_SHA.upper())
    p.runs[0].font.size = Pt(8)
    para(doc, "Новые снимки от 1 октября показывают локальные VI из ACQUISITION_VIs_verified. Снимки главного VI от 22 сентября получены в LabVIEW 2012 через RDP. Их имена сохранены в подписях. Совпадение сегодняшнего работающего экземпляра на XP с копией не проверялось.")
    para(doc, "После паузы в ACQUISITION_VIs_verified обнаружены другие SHA256 у 0_ACQ_ELYSE.vi и 1_Focales ON.vi. Причина и семантические отличия не установлены; эти файлы не перезаписывались. Исходный LLB и все 17 архивных членов сохранены без изменений. Продолжение нативного просмотра из исходного LLB заблокировано ошибкой активации окна выбора файла; новых снимков после этого сбоя нет.")
    para(doc, "Порядок исполнения определяется проводом задачи, кластером ошибок, границами последовательности и условиями Case. Пространственное положение узлов не задаёт порядок. Wait и локальное присваивание в одном кадре могут выполняться параллельно; длительность кадра не является доказанной шириной физического импульса.")
    table(("Уровень", "Значение"), (
        ("Наблюдение", "Узел, провод или значение видны на нативном снимке."),
        ("Проверка исходника", "UID, терминалы и провод проверены в экспортированном BDHb с фиксированным SHA256."),
        ("Вывод", "Следствие этих связей при указанном условии входа."),
        ("Не установлено", "Отсутствует нужный снимок, привязка терминала или проверка внешнего результата."),
    ), (1.7, 5.1))
    para(doc, "Нормализованный JSON не принят за окончательную схему проводов. Он ошибочно описывает NI6220 как восьмиканальный и связывает входы диапазона с неподключёнными константами ±0.2. Нативный рисунок ниже показывает 16 каналов и провода от таблиц Min/Max.")

    page("Начало инициализации и синхронизация времени")
    para(doc, "В 0_ACQ_ELYSE.vi внешний кадр 1 содержит внутреннюю последовательность 0–5. Её кадр 0 выполняет плоскую двухкадровую последовательность: сначала Wait 200 ms, затем System Exec.vi с командой синхронизации времени. Это системная операция на Acquisition, не соединение PSP.")
    shot(OLD / "EV-ACQ-0002-outer1-init-inner0-time-sync.png", "0_ACQ_ELYSE.vi путь 1/0", (325, 438, 890, 622))
    para(doc, r"Команда источника: net time \\10.20.30.2 /set /y. Ошибка System Exec поступает в обработчик. Рисунок подтверждает наличие обработки, но сам по себе не доказывает, что сбой синхронизации блокирует следующие кадры.")
    para(doc, "Вывод для модели: синхронизация времени — отдельный переход до создания задач; её успех не следует подменять успехом подключения Shared Variables.")

    page("Порядок вызова инициализаторов карт")
    para(doc, "Во внутреннем кадре 1 жёлтый провод проходит через NI6602, NI6071E, DIO96 и NI6703. Ссылки задач сохраняются в отдельных локальных банках. NI6071E получает 10 отсчётов на канал, 5000 Hz и источники запуска /1/PFI0 и /2/PFI0.")
    shot(OLD / "EV-ACQ-0003-init-daqmx-cards.png", "0_ACQ_ELYSE.vi путь 1/1", (65, 215, 1245, 570))
    para(doc, "Показаны ветви Pas d’erreur. В предыдущем нативном обходе все четыре Erreur содержали Clear Errors.vi; отдельных снимков этих четырёх ветвей в данном наборе нет. Поэтому текст о них — запись предыдущего наблюдения, а не новое покадровое доказательство.")
    para(doc, "NI6220 создаётся позже, в 1/5/3. Следовательно, отсутствие этого узла на рисунке не означает, что одиннадцатая карта пропущена. NI6259 присутствует в библиотеке, но в установленном статическом пути инициализации не используется.")

    page("Восемь задач NI6602 и заданные времена")
    para(doc, "1_ACQ_INIT_NI6602.vi содержит восемь кадров 0–7. Каждый создаёт одну задачу CO Pulse Ticks на /10/ctrN с timebase /10/PFI11, начальной задержкой 0, повторным цифровым запуском и одним конечным импульсом. Низкий исходный уровень и Rising для активного фронта timebase заданы явно.")
    table(("OUT", "Low ticks", "High ticks", "PFI", "Start"), [
        (str(n), str(low), str(high), str(trigger) + (" ↑" if edge == "rising" else " ↓"), "Да" if started else "Нет")
        for n, low, high, trigger, edge, started, _meaning in COUNTERS
    ], (.5, 1.4, 1.6, 1.5, 1.8))
    para(doc, "При timebase 20 MHz один тик равен 0.05 µs. Например, OUT3: 43658 тиков = 2182.9 µs низкого интервала; 60 тиков = 3 µs высокого. Это расчёт заданного счётчику времени, не измерение импульса.")
    para(doc, "Сводная таблица внутри VI не совпадает с проводами для OUT0, OUT3 и OUT4: она показывает соответственно Low=200 вместо 31, Low=43444 вместо 43658 и High=56 вместо 60. В последующих страницах используются именно подключённые константы выбранного кадра.")
    para(doc, "OUT3 и OUT4 не имеют Start Task в инициализации. Их задача создана и настроена, но здесь не запущена. Остальные шесть кадров заканчиваются Start Task. Это различие сохраняется в Python-плане.")

    for pair in range(4):
        page(f"NI6602 кадры {pair*2} и {pair*2+1}")
        for n, low, high, trigger, edge, started, meaning in COUNTERS[pair*2:pair*2+2]:
            doc.add_heading(f"OUT{n} {meaning}", 2)
            shot(NEW / f"INIT-NI6602-frame{n}.png", f"1_ACQ_INIT_NI6602.vi кадр {n} из 0–7", (65, 93, 1050, 475), 6.65)
            para(doc, f"/10/ctr{n}; запуск /10/PFI{trigger}, {'Rising' if edge == 'rising' else 'Falling'}; Low={low}, High={high} тиков. "
                 f"При 20 MHz: {low*.05:g} µs и {high*.05:g} µs. "
                 + ("После Implicit finite 1 следует Start Task." if started else "После Implicit finite 1 Start Task отсутствует."))

    page("NI6071E входы и создание задачи C1")
    para(doc, "В 1_ACQ_INIT_NI6071E.vi кадр 0 содержит терминалы двух задач, двух триггеров, числа отсчётов, частоты и ошибок. Он не выполняет создание каналов. Кадр 1 создаёт C1; кадр 2 последовательно создаёт C2.")
    shot(NEW / "INIT-NI6071E-frame0.png", "1_ACQ_INIT_NI6071E.vi кадр 0", (120, 305, 435, 550), 2.3)
    shot(NEW / "INIT-NI6071E-frame1-C1.png", "1_ACQ_INIT_NI6071E.vi кадр 1 C1", (15, 180, 1230, 625), 6.8)
    para(doc, "Create Task → For N=64 с AI Voltage → Sample Clock → Start Digital Edge → свойства Read. Режим RSE. Индексируемые туннели подают канал и Min/Max. Снимок показывает ai2 = ±0.05 V; полный raw XML дополнительно подтверждает ai3/ai4 = ±1 V и остальные 61 канал = ±10 V. Физический массив: 1/ai0…63.")
    para(doc, "Clock=OnboardClock, фронт Rising, конечное число отсчётов. Источник Start поступает с терминала Trigger C1. RelativeTo=текущая позиция чтения, AutoStart=True. Создание задачи не равно выполненному чтению.")

    page("NI6071E создание задачи C2")
    shot(NEW / "INIT-NI6071E-frame2-C2.png", "1_ACQ_INIT_NI6071E.vi кадр 2 C2", (15, 180, 1230, 625), 6.8)
    para(doc, "Кадр 2 создаёт вторую задачу с For N=64 и тем же режимом RSE. Он получает независимый Trigger C2. Число отсчётов и частота общие для двух задач; при родительском вызове это 10 и 5000 Hz.")
    para(doc, "Ссылка C2 выходит из узла Read Property, а кластер ошибок связан с предыдущим кадром и обработчиком. Порядок C1 → C2 обеспечен внешней последовательностью. Вызов AutoStart=True здесь записывает настройку свойства чтения; отдельного DAQmx Start Task на рисунке нет.")
    para(doc, "Нативные кадры показывают RSE, хотя прежний subvi_contracts.md называл differential. Raw XML подтверждает 2/ai0…63 и ±10 V для всех 64 каналов C2. Оба Create Task имеют auto cleanup=True. Проверка validate_acq_ni6071e_initializer.py закрепляет массивы и провода; 18 офлайн-тестов проверяют исходник и отвергают изменения значений и связей.")
    para(doc, "Вход error in и выход error out этого VI не подключены; локальных обращений к ним также нет. Ошибка C1 идёт через sequence local 310 к Create Task C2, затем к Simple Error Handler. Его выход ошибки не подключён. Поэтому внешний error out не передаёт эту цепочку и не подтверждает успешную инициализацию. Оба For используют обычные туннели ошибок без shift register: ошибка раннего канала может не попасть в результат последней итерации.")

    page("DIO96 шесть задач для трёх карт")
    shot(NEW / "INIT-DIO96-six-tasks.png", "1_ACQ_INIT_DIO96.vi полная диаграмма", (80, 95, 1080, 530))
    table(("Задача", "Физические порты", "Линий"), (
        ("C3 DI", "/3/port0:6", "56"), ("C4 DI", "/4/port0:7", "64"), ("C5 DI", "/5/port0:6", "56"),
        ("C3 DO", "/3/port7:11", "40"), ("C4 DO", "/4/port8:11", "32"), ("C5 DO", "/5/port7:11", "40"),
    ), (1.4, 3.7, 1.7))
    para(doc, "Провод ошибок проходит по верхней строке слева направо, затем по нижней. В каждом звене Create Task предшествует созданию цифровых каналов. Шесть ссылок объединяются в ID Cx_DIO. True у Create Task задаёт auto cleanup.")
    para(doc, "В этом инициализаторе нет DAQmx Write. Начальная запись DO выполняется позднее другим VI. Это отделяет распределение ресурсов от изменения выходного состояния.")

    for pair in range(2):
        page(f"NI6703 задачи C{6+pair*2} и C{7+pair*2}")
        for n in range(6+pair*2, 8+pair*2):
            shot(NEW / f"INIT-NI6703-frame{n-6}-C{n}.png", f"1_ACQ_INIT_NI6703.vi кадр {n-6} C{n}", (350, 160, 1140, 425), 6.65)
            para(doc, f"Create Task C{n} → For N=10 → AO Voltage с -10 и +10 V → поле C{n}_NI6703 в ID 4xNI6703. Физические каналы относятся к /{n}/ao0…9; полная строка не помещается в узком элементе массива на снимке.")
        para(doc, "Таблицы Vmin/Vmax/Pente/Offset в нижней части полной диаграммы не подключены к входам создания AO. Настройки диапазона задачи — непосредственно -10 и +10 V. Масштабирование логических величин выполняет 1_ACQ_WRITE_NI6703.vi, не этот For.")

    page("Проверка NI6071E и резервные источники запуска")
    shot(OLD / "EV-ACQ-0004-init-test-20mhz-ni6071e.png", "0_ACQ_ELYSE.vi путь 1/2 ветвь Erreur", (88, 355, 1035, 780))
    para(doc, "После создания C1/C2 главный VI вызывает 1_ACQ_READ_NI6071E.vi. При Erreur следуют Clear Errors → Clear Task C1 → Clear Task C2 → INIT_NI6071E. Резервные /1/20MHzTimebase и /2/20MHzTimebase поданы на Start Digital Edge, не на Sample Clock: он остаётся OnboardClock с 5000 Hz и 10 отсчётами. За повторным INIT стоит Case с Clear Errors.")
    para(doc, "Комментарий упоминает -200284 при отсутствии 20 MHz pilot. Однако провод выбирает ветвь по кластеру ошибок, а не по видимому сравнению error.code == -200284. Поэтому нельзя ограничивать этот переход только одним кодом ошибки.")
    para(doc, "Это один резервный INIT без повторного тестового READ или retry-loop в данном кадре. Его вход error in внутри subVI не используется: родительский провод не доказывает прерывание инициализации при ошибке Clear Task. Python-модель должна различать две конфигурации запуска и не выдавать успешную переинициализацию без отдельного подтверждения.")

    page("Shared Variables отключённая карта и активное открытие")
    shot(OLD / "EV-ACQ-0005-init-psp-disabled-map.png", "0_ACQ_ELYSE.vi путь 1/3 Désactivé", (85, 255, 1205, 840), 5.75)
    para(doc, "Прямой список привязок находится в Diagram Disable. Он полезен для чтения имён, но не является выполняемым этапом подключения. Активная сторона этой структуры пустая.")
    shot(OLD / "EV-ACQ-0006-init-dynamic-psp-discovery.png", "0_ACQ_ELYSE.vi путь 1/4 активное открытие", (90, 280, 940, 498), 6.6)
    para(doc, "Активный путь обнаруживает переменные под ni.var.psp://10.20.30.2/SUPERVISION, читает TypeDonnées, открывает ссылки и собирает Refnum SVE 2. В For виден Wait 1 ms. Перечисление, типизация и открытие — реальные узлы; порядок выдачи переменных и последствия частичного сбоя отдельно не доказаны.")

    page("Начальные логические команды AO и DO")
    shot(OLD / "EV-ACQ-0007-init-output-state-inner0.png", "0_ACQ_ELYSE.vi путь 1/5/0", (245, 270, 1000, 840), 5.55)
    table(("Банк", "Поля отличающиеся от нуля или False"), (
        ("C6 и C7", "Нет; по 10 нулей"), ("C8", "[1]=21; [2]=27.9; [6]=360"),
        ("C9", "[0]=6.5; [2,3]=4.755; [4,5,6]=2.126"),
        ("C3 DO", "[1,4]=True"), ("C4 DO", "[1,4,6,8,17,19]=True"), ("C5 DO", "[33]=True"),
    ), (1.1, 5.7))
    para(doc, "Банки содержат 152 поля: 40 AO и 112 DO. Из них 18 ненулевые или True, 134 нулевые или False. Подписи литералов C3/C5 в VI перепутаны; привязка таблицы установлена по проводам к целевым локальным банкам и их типам, а не по подписи константы.")

    page("Публикация команд и первый обмен с картами")
    shot(OLD / "EV-ACQ-0008-startup-psp-output-writes.png", "0_ACQ_ELYSE.vi путь 1/5/1", (90, 270, 1210, 740), 6.2)
    para(doc, "Подкадр 1 публикует C6–C9 и C3–C5 выходные банки через Shared Variables. Публикация команды не является подтверждением результата на карте.")
    shot(OLD / "EV-ACQ-0009-startup-initial-daq-io.png", "0_ACQ_ELYSE.vi путь 1/5/2", (105, 290, 1160, 675), 6.2)
    para(doc, "Следующий подкадр вызывает READ_NI6071E → RW_DIO96 → WRITE_NI6703 по проводу ошибок. RW_DIO96 сначала читает три DI банка, затем пишет три DO. WRITE_NI6703 преобразует логические величины и выполняет AO-запись. Именно этот этап делает инициализацию потенциально актуирующей.")

    page("Инициализация TPG300 NI6220 и флагов")
    shot(OLD / "EV-ACQ-0010-startup-vacuum-ni6220-ui-gates.png", "0_ACQ_ELYSE.vi путь 1/5/3", (90, 245, 1225, 865), 6.5)
    para(doc, "Подкадр 3 создаёт две TPG300 сессии для COM1 и COM2, инициализирует NI6220 и присваивает начальные UI и процедурные флаги. Родительский провод к Baud Rate содержит selector 4; библиотечная таблица [300,1200,2400,4800,9600,19200,38400] преобразует его в 9600 baud.")
    para(doc, "Для TPG300 обнаружены состояния Init & Test, Next Baud Rate, Set Default, Communication OK и Error Box. Их полные переходы, retry limit и каждый вложенный кадр пока не подтверждены отдельными рисунками в этом документе. Они не подменяются пустой Python-функцией с якобы успешной инициализацией.")

    page("NI6220 шестнадцать каналов и реальная связь диапазонов")
    shot(NEW / "INIT-NI6220-full.png", "1_ACQ_INIT_NI6220.vi полная диаграмма", (105, 155, 1385, 610))
    para(doc, "Физический массив содержит 11/ai0…11/ai15. Array Size подаётся на N цикла For. Массивы Min и Max входят через индексируемые туннели и проводами доходят до AI Voltage. Внутренние константы -0.2 и +0.2 стоят без проводов и не задают общий диапазон всех каналов.")
    table(("Индексы", "Min", "Max"), (("0–3 и 8–15", "-0.2 V", "+0.2 V"), ("4–7", "-10 V", "+10 V")), (3.2, 1.8, 1.8))
    para(doc, "Режим RSE; OnboardClock; конечные отсчёты; Rising; цифровой Start от /11/PFI0; RelativeTo=текущая позиция чтения; AutoStart=True. Число отсчётов и частота приходят через терминалы VI. Их значения у конкретного родительского вызова требуют отдельного крупного снимка или raw-terminal проверки, а не переноса значений по умолчанию.")
    para(doc, "Это отрицательная проверка парсера: нормализованный JSON одновременно уменьшает массив до 8 каналов и неверно назначает неподключённые константы источниками диапазона. Такие связи нельзя использовать для изменения Python-плана.")

    page("Последние публикации и смысл начального напряжения")
    shot(OLD / "EV-ACQ-0011-startup-dps-eps-vdma-writes.png", "0_ACQ_ELYSE.vi путь 1/5/4", (175, 240, 930, 840), 5.7)
    para(doc, "Последний подкадр публикует DPS, EPS и VDM-A, выполняет проверку наличия pilot и содержит Wait 100 ms. Затем внешний кадр 2 запускает параллельные рабочие циклы. Это завершение последовательности инициализации, не свидетельство исправности каждого устройства.")
    para(doc, "В начальном C9[0] задано 6.5. В WRITE_NI6703 соответствующая линейная шкала имеет коэффициент 0.5 и offset 0; условный запрос /9/ao0 равен 3.25 V. Логическая команда HT и напряжение DAC — разные числа.")
    para(doc, "Даже нулевая логическая команда не всегда означает 0 V DAC. Нелинейные каналы C8[3] и C8[4] дают соответственно 2.1775 и 3.8587 V при x=0. Эти расчёты проверены отдельным преобразователем; нативные кадры обеих нелинейных ветвей writer ещё не включены в данный набор снимков.")

    page("Условия входа в общую остановку")
    shot(OLD / "EV-ACQ-0013-outer3-emergency-stop-overview.png", "0_ACQ_ELYSE.vi внешний кадр 3 две параллельные While", (0, 135, 1240, 975), 5.55)
    para(doc, "Внешний кадр 3 начинается после выхода пяти рабочих While из кадра 2. TCP ED=True открывает две параллельные While; False оставляет пустую ветвь. В нижней While Arrêt général=True выбирает семь фаз; False только разрешает пять UI-контролов. Эти два условия нельзя пропустить в переносе.")
    para(doc, "Верхняя While продолжает READ_NI6071E → RW_DIO96 → WRITE_NI6703 с Wait 50 ms. Нижняя меняет локальные командные банки. Обе завершаются по stop urgence. Поэтому локальная запись команды останова и её перенос на NI выполняются разными параллельными ветвями.")

    page("Фаза 0 снижение логической команды HT")
    shot(OLD / "EV-ACQ-0041-emergency00-ramp-ht-to-6-5kv.png", "Остановка фаза 0", (250, 510, 905, 925), 6.4)
    para(doc, "While читает C9[0] и сравнивает команду с 6.6. Если command < 6.6, True ветвь завершает While без следующей записи C9. Иначе False ветвь вычитает 0.1, пересобирает C9, записывает локальный банк и содержит Wait 500 ms. Отдельного ограничения числа итераций на проводе выхода нет.")
    para(doc, "Сравнение использует команду, не показание HT. Например, при стартовой команде 6.5 цикл выйдет без снижения. Получение физического напряжения ниже порога из этого не следует. Для NaN/нечислового состояния и внешних конкурентных записей завершение не доказано.")
    para(doc, "Raw-wire проверка: validate_acq_controlled_stop_ht_ramp.py — PASS. Два вспомогательных числовых local paramIdx 48 и 50 также получают значения; их бизнес-имена независимо не установлены.")

    page("Фаза 1 остановка импульсов NI6602")
    shot(OLD / "EV-ACQ-0013-outer3-emergency-stop-overview.png", "Фаза 1 вложенный кадр 0 остановка OUT3", (270, 510, 890, 928), 6.3)
    table(("Кадр", "Проверенная операция"), (
        ("0", "OUT3: poll CO.PulseDone == True OR i > 40; Wait 1 ms; затем Stop Task → Clear Errors"),
        ("1", "OUT4: такой же poll; затем Stop Task → Clear Errors"),
        ("2", "Wait 1000 ms"),
    ), (.6, 6.2))
    para(doc, "Порядок OUT3 → OUT4 → ожидание задан вложенной последовательностью. Ограничение i>40 позволяет перейти к попытке Stop Task даже без положительного PulseDone. Наличие Clear Errors не подтверждает успешную остановку.")
    para(doc, "validate_acq_controlled_stop_pulse_sync.py — PASS. Все три кадра дополнительно просмотрены нативно; отдельные снимки приведены в приложении. Это подтверждение проводов, не успешной остановки реального OUT.")

    page("Фаза 2 команда останова источника HT")
    shot(OLD / "EV-ACQ-0036-emergency02-stop-ht-supply.png", "Фаза 2 вложенный кадр 0", (255, 510, 900, 925), 6.3)
    table(("Кадр", "Действие"), (("0", "C4_OUT_DIO96[19]=False и Wait 150 ms в одном кадре"),
                               ("1", "C4_OUT_DIO96[19]=True"), ("2", "Wait 1000 ms")), (.6, 6.2))
    para(doc, "Пара False → True — логическая команда поля «Arrêt alimentation HT modulateur». Она достигает аппаратной записи через параллельную read/write While. Внутри кадра 0 Wait и локальный writer не связаны друг с другом; точно 150 ms физического уровня из рисунка не следует.")
    para(doc, "validate_acq_controlled_stop_ht_supply.py — PASS для всех трёх кадров и маркеров фаз 6,5,4,3,2,1,0. Все три кадра дополнительно просмотрены нативно и показаны в приложении.")

    page("Фаза 3 обнуление выбранных магнитных команд")
    shot(OLD / "EV-ACQ-0037-emergency03-zero-magnets.png", "Фаза 3 вложенный кадр 0", (250, 510, 980, 925), 6.4)
    table(("Кадр", "Действие"), (
        ("0", "C6[0–7,9]=0; C7[0,1,3–9]=0"), ("1", "Wait 1000 ms"),
        ("2", "C3 DO[9,11,15,17,21,23,25,27,29,31–39]=False"), ("3", "Wait 1000 ms"),
    ), (.6, 6.2))
    para(doc, "Не обнуляются C6[8] и C7[2]. Поэтому точное следствие — обнуление выбранных полей, а не всех каналов C6/C7. В C3 изменяются 18 выбранных битов; весь цифровой банк не перезаписывается константой False.")
    para(doc, "validate_acq_controlled_stop_magnets.py — PASS. Все четыре кадра дополнительно просмотрены нативно и показаны в приложении.")

    page("Фаза 4 пятнадцать кадров остановки модулятора")
    shot(NEW / "STOP-phase4-frame0.png", "Фаза 4 вложенный кадр 0 из 0–14", (205, 435, 910, 915), 5.5)
    table(("Кадры", "C4 DO False затем True", "Следующий Wait"), (
        ("0,1,2", "[8] Arrêt focale", "1000 ms"),
        ("3,4,5", "[17] Arrêt relais HT", "1000 ms"),
        ("6,7,8", "[6] Arrêt prémagnétisation", "1000 ms"),
        ("9,10,11", "[4] Arrêt chauffage", "2000 ms"),
        ("12,13,14", "[1] Arrêt général basse tension", "1000 ms"),
    ), (1.1, 3.8, 1.9))
    para(doc, "Снимок кадра 0 показывает 150 ms через туннель последовательности к Wait. Raw-проверка validate_acq_controlled_stop_wait_tunnels.py прослеживает тот же источник во всех пяти False-кадрах 0,3,6,9,12. Сумма явных Wait этой фазы: 6750 ms. Это программные задержки, не доказанная длительность физических импульсов или всей фазы.")
    para(doc, "validate_acq_controlled_stop_stage_pulses.py — PASS. Кадры 0 и 1 показаны в приложении; нативные снимки кадров 2–14 ещё требуются.")

    page("Фаза 5 восемь кадров остановки воды")
    shot(OLD / "EV-ACQ-0039-emergency05-stop-cooling.png", "Фаза 5 вложенный кадр 7 из 0–7", (250, 510, 900, 925), 5.5)
    table(("Кадр", "Действие"), (
        ("0,1", "C3 DO[1] False затем True — arrêt Canon"),
        ("2", "Wait 400 ms"), ("3,4", "C3 DO[4] False затем True — arrêt Section"),
        ("5 и 6", "Оба кадра: EPS[3,2,5,1]=False,False,True,False; DPS[1]=False"),
        ("7", "Wait 100 ms"),
    ), (.8, 6))
    para(doc, "Статусы в кадрах 5 и 6 действительно повторяются. В этой вложенной последовательности нет прямого PSP writer. Локальное присваивание статуса не подтверждает прекращение потока и не является само по себе доставленным статусом Supervision.")
    para(doc, "Рисунок показывает кадр 7 с Wait 100 ms. Raw-wire проверки cooling и wait_tunnels — PASS: Wait в кадрах 0,3,4 равен 150 ms, включая восстановление C3[4]=True в кадре 4. Сумма явных Wait: 950 ms, не физическая длительность остановки. Нативные снимки кадров 0–6 ещё требуются.")

    page("Фаза 6 и отдельное закрытие ссылок")
    shot(OLD / "EV-ACQ-0040-emergency06-final-stop.png", "Остановка фаза 6", (250, 510, 900, 925), 5.45)
    para(doc, "Один кадр задаёт local paramIdx 50=0, stop urgence=True, Arrêt général=False и Wait 1000 ms. Независимые узлы не задают порядок «сначала ждать, затем остановить». Оба stop-terminal внешних While читают stop urgence. Проверка validate_acq_controlled_stop_completion.py — PASS.")
    page("Закрытие ссылок после остановки")
    shot(OLD / "EV-ACQ-0014-cleanup-psp-tpg300.png", "0_ACQ_ELYSE.vi внешний кадр 4", (175, 245, 985, 735), 5.6)
    para(doc, "Следующий внешний кадр закрывает массив ссылок PSP через For, вызывает TPG300 Close для двух сессий и задаёт stop=False. Здесь не показан DAQmx Clear Task. Это не доказывает утечку: Create Task использует auto cleanup, а вызовы в других областях требуют отдельной проверки.")
    para(doc, "Закрытие ресурсов и остановка оборудования — разные процедуры. Кадр 4 не следует описывать как универсальное снятие напряжений.")

    page("Обычная команда останова и условная семифазная процедура")
    para(doc, "Supervision Arrêt MOD записывает DPS[3]. Acquisition выбирает соответствующий event 6 Arrêt GENERAL Mod. Это другой путь, чем внешний кадр 3 с TCP ED и Arrêt général.")
    table(("Признак", "Event 6", "Внешний кадр 3"), (
        ("Инициатор", "DPS[3] через dispatcher", "TCP ED=True и Arrêt général=True после runtime"),
        ("Focales OFF", "Есть вызов перед C4 импульсами", "Нет вызова внутри семи фаз"),
        ("C4 stop пары", "8,17,6,4,1", "8,17,6,4,1"),
        ("Прямой DPS PSP writer", "Есть в последнем кадре", "Нет внутри семи фаз"),
    ), (1.6, 2.6, 2.6))
    para(doc, "В корневом графе не обнаружен локальный writer Arrêt général=True. PSP write-error пути задают stop=True и TCP ED=True, но не этот флаг. Следовательно, переход к семифазной процедуре при любом сбое связи не доказан. Не следует автоматически привязывать к ней кнопку Arrêt MOD или объявлять её проверенной аварийной остановкой.")
    para(doc, "Сравнение проверяется validate_acq_two_stop_paths.py и validate_acq_stop_ingress.py. Event 6, аппаратные входы радиопротекции, их реакции и дополнительные аварийные пути остаются самостоятельными предметами покадрового подтверждения.")

    page("Что подтверждено и какие рисунки ещё нужны")
    table(("Область", "Нативные снимки", "Оставшаяся проверка"), (
        ("Пять инициализаторов NI", "17 кадров из 17 видимых", "C1/C2 полностью проверены raw XML; нужны полные строки AO и остальные error-paths"),
        ("Главная инициализация", "10 снимков основных этапов", "Четыре Erreur после init; пустые error-arms; крупные аргументы NI6220"),
        ("Остановка семь фаз", "Все кадры фаз 1–3; фаза 4 кадры 0–1; выбранные кадры остальных фаз", "20 остальных вложенных кадров"),
        ("Финальное закрытие", "Один снимок внешнего кадра 4", "Все error-paths TPG Close и неявная очистка DAQ"),
        ("TPG300", "Родительские вызовы", "Полный собственный state machine и retry/ошибки"),
    ), (1.6, 2.2, 3))
    para(doc, "Недостающие снимки вложенной остановки: фаза 4 кадры 2–14 и фаза 5 кадры 0–6. Всего 13+7=20. Дополнительно нужны оба Case фазы 0 и пустые ветви условий входа. Raw-wire тесты не заменяют требуемую визуальную проверку каждого кадра.")
    para(doc, "Семь hash-pinned проверок stop-фаз и дополнительные проверки входа останова, туннелей Wait, init error-gates, fallback и внутреннего NI6071E закрепляют доказанные пути. SHA256 LLB и всех 17 архивных VI проверены; восемь строк ni6602_timing.csv совпали со снимками. Два рабочих распакованных VI отличаются от манифеста. Аппаратный эксперимент не выполнялся.")
    para(doc, "Следующее доказательство должно закрыть указанные кадры и собственные TPG300 ветви. После этого отдельно проверяются обычный event 6, входы аварийного останова и прохождение ошибок через параллельные циклы. До завершения этих пунктов полная эквивалентность инициализации и деинициализации Python не установлена.")

    captured_stop = [(phase, frame) for phase, count in ((1, 3), (2, 3), (3, 4), (4, 2))
                     for frame in range(count)]
    for pair in range(0, len(captured_stop), 2):
        entries = captured_stop[pair:pair+2]
        page("Нативные кадры остановки " + " и ".join(f"{phase} {frame}" for phase, frame in entries))
        for phase, frame in entries:
            shot(NEW / f"STOP-phase{phase}-frame{frame}.png",
                 f"0_ACQ_ELYSE.vi фаза {phase} кадр {frame}", (205, 435, 910, 915), 5.75)

    # Accessibility keeps the original figure meaning with each embedded image.
    for inline in doc.inline_shapes:
        inline._inline.docPr.set("descr", "Нативная диаграмма LabVIEW; исходный файл и область указаны в подписи.")
    doc.core_properties.title = "ELYSE Acquisition инициализация карт и проверка остановки"
    doc.core_properties.subject = "Нативные диаграммы и проверка сохранённых проводов без выполнения VI"
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.save(OUTPUT)
    with LEDGER.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(figures[0]))
        writer.writeheader()
        writer.writerows(figures)
    report.update({"output": str(OUTPUT), "docx_sha256": sha(OUTPUT), "figures": len(figures),
                   "planned_pages": page_no, "native_stop_nested_frames_missing": 20,
                   "new_native_stop_captures": len(captured_stop),
                   "render_verified": False})
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
