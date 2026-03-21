from pathlib import Path

from openpyxl import Workbook


OUTPUT_PATH = Path(__file__).with_name("german_ar_export.xlsx")
HEADERS = [
    "Rechnungsnummer",
    "Kundenname",
    "Rechnungsdatum",
    "Fälligkeitsdatum",
    "Bruttobetrag",
    "Offener Betrag",
    "Währung",
]
ROWS = [
    ["RE-2026-001", "Müller Bau GmbH", "15.01.2026", "14.02.2026", "45.000,00", "45.000,00", "EUR"],
    ["RE-2026-002", "Böhm Handel AG", "18.01.2026", "17.02.2026", "12.500,00", "12.500,00", "EUR"],
    ["RE-2026-003", "Schäfer Logistik e.K.", "20.01.2026", "19.02.2026", "9.876,54", "0,00", "EUR"],
    ["RE-2026-004", "Krüger Maschinenbau GmbH", "22.01.2026", "21.02.2026", "7.250,00", "3.100,00", "EUR"],
    ["RE-2026-005", "Jäger Elektronik AG", "25.01.2026", "24.02.2026", "1.234,56", "1.234,56", "EUR"],
    ["RE-2026-006", "Fröhlich Consulting GmbH", "27.01.2026", "26.02.2026", "950,00", "950,00", "EUR"],
    ["RE-2026-007", "Weiß & Söhne KG", "01.02.2026", "03.03.2026", "18.765,40", "18.765,40", "EUR"],
    ["RE-2026-008", "Küster Pharma GmbH", "05.02.2026", "07.03.2026", "2.499,99", "499,99", "EUR"],
    ["RE-2026-009", "Hübner Solar AG", "10.02.2026", "12.03.2026", "3.300,00", "3.300,00", "EUR"],
    ["RE-2026-010", "Döring Verkehr GmbH", "14.02.2026", "16.03.2026", "6.543,21", "6.543,21", "EUR"],
]


def main() -> None:
    workbook = Workbook()
    invoices_sheet = workbook.active
    invoices_sheet.title = "Rechnungen"
    invoices_sheet.append(HEADERS)
    for row in ROWS:
        invoices_sheet.append(row)

    summary_sheet = workbook.create_sheet("Zusammenfassung")
    summary_sheet.append(["Gesamt", "107.919,70"])

    workbook.save(OUTPUT_PATH)


if __name__ == "__main__":
    main()
