# Sample AR Export Files

Synthetic test files mimicking real accounting tool exports. Used for developing and testing the ingestion engine (Milestone 2+). Real exports from paying customers will replace these during pilot.

## Files

### pohoda_ar_export.csv
- **Mimics:** Pohoda (Czech accounting software)
- **Format:** Semicolon-delimited, Czech headers, DD.MM.YYYY dates, Czech encoding
- **Edge cases:** Same customer with different name spellings (ACME s.r.o. vs ACME SRO), partial payment (row 4), one paid invoice (row 15 has 0.00 remaining)
- **Rows:** 15 invoices, 10 unique customers

### fakturoid_ar_export.csv
- **Mimics:** Fakturoid (Czech cloud invoicing tool, English export)
- **Format:** Comma-delimited, English headers, ISO dates (YYYY-MM-DD), EUR currency
- **Edge cases:** Multi-country customers (CZ, DE, FR, IT, ES, AT, PL), name variants (ACME Czech s.r.o. vs ACME Czech sro), partial payment, one paid invoice
- **Rows:** 15 invoices, 10 unique customers

### messy_generic_export.csv
- **Mimics:** A poorly formatted export from a generic Czech accounting tool
- **Format:** Comma-delimited, Czech headers, D.M.YYYY dates, Czech number formatting (space thousands, comma decimals), quoted fields with commas
- **Edge cases:** Missing company name (row 11), missing DIC/VAT (rows 2, 6), missing contact info, extra whitespace in company names, different casing (beta trading vs Beta Trading), company name with comma in quotes, notes column with free text
- **Rows:** 12 invoices, 8 unique customers

## What the ingestion engine must handle

1. Semicolon AND comma delimiters
2. Czech AND English headers
3. DD.MM.YYYY AND YYYY-MM-DD AND D.M.YYYY date formats
4. Czech number formatting ("45 000,00") AND standard ("45000.00")
5. Customer name variants that should be fuzzy-matched
6. Missing fields (no email, no VAT, no company name)
7. Partial payments (amount due < total amount)
8. Already-paid invoices (amount due = 0)
