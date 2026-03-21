# Sample AR Export Files

Synthetic test files covering the major European accounting export formats. Used for developing and testing the ingestion engine (Milestone 2+). Real exports from paying customers will replace these during pilot.

## Files

### pohoda_ar_export.csv
- **Mimics:** Pohoda (Czech accounting software)
- **Format:** Semicolon-delimited, Czech headers, DD.MM.YYYY dates, standard decimal numbers, UTF-8
- **Edge cases:** Same customer with different name spellings (ACME s.r.o. vs ACME SRO), partial payment, one fully paid invoice (0.00 remaining)
- **Rows:** 15 invoices, 10 unique customers

### fakturoid_ar_export.csv
- **Mimics:** Fakturoid (Czech cloud invoicing tool, English-language export)
- **Format:** Comma-delimited, English headers, ISO dates (YYYY-MM-DD), standard decimal numbers, EUR, UTF-8
- **Edge cases:** Multi-country customers (CZ, DE, FR, IT, ES, AT, PL), name variants (ACME Czech s.r.o. vs ACME Czech sro), partial payment, one fully paid invoice
- **Rows:** 15 invoices, 10 unique customers

### messy_generic_export.csv
- **Mimics:** A poorly formatted export from a generic accounting tool
- **Format:** Comma-delimited, Czech headers, D.M.YYYY dates, space+comma numbers ("45 000,00"), quoted fields with commas, UTF-8
- **Edge cases:** Missing company name, missing VAT, missing contact info, extra whitespace in names, inconsistent casing, company name with comma in quotes, notes column with free text
- **Rows:** 12 invoices, 8 unique customers

### french_ar_export.csv
- **Mimics:** French accounting tool export (Sage, Cegid, generic ERP)
- **Format:** Semicolon-delimited, French headers, DD/MM/YYYY dates, space+comma numbers ("12 500,00"), EUR, Windows-1252 encoding
- **Edge cases:** Accented characters (â, è, é), company name variants with/without accents and legal suffixes (SARL/SAS/SA/EURL/SCI), ampersand vs word ("& Fils" vs "et Fils"), partial payment, one fully paid, SIRET numbers (14-digit, must remain string)
- **Rows:** 12 invoices, 8 unique customers

### italian_ar_export.csv
- **Mimics:** Italian accounting tool export (Fatture in Cloud, TeamSystem, generic ERP)
- **Format:** Semicolon-delimited, Italian headers, DD/MM/YYYY dates, dot+comma numbers ("45.000,00"), EUR, UTF-8
- **Edge cases:** Legal suffix variants (S.r.l. vs Srl vs no suffix), dot+comma number format (dot as thousands separator), Partita IVA with IT prefix (must remain string), partial payment, one fully paid
- **Rows:** 12 invoices, 8 unique customers

## Format coverage matrix

| Pattern | Example | Files that test it |
|---------|---------|-------------------|
| Semicolon delimiter | `;` | pohoda, french, italian |
| Comma delimiter | `,` | fakturoid, messy |
| DD.MM.YYYY dates | `01.03.2026` | pohoda |
| D.M.YYYY dates | `3.1.2026` | messy |
| YYYY-MM-DD dates | `2026-03-01` | fakturoid |
| DD/MM/YYYY dates | `03/01/2026` | french, italian |
| Plain dot decimal | `45000.00` | pohoda, fakturoid |
| Space thousands + comma decimal | `45 000,00` | messy, french |
| Dot thousands + comma decimal | `45.000,00` | italian |
| Comma thousands + dot decimal | `45,000.00` | inline unit test (no fixture) |
| UTF-8 encoding | | pohoda, fakturoid, messy, italian |
| Windows-1252 encoding | | french |
| Czech headers | | pohoda, messy |
| English headers | | fakturoid |
| French headers | | french |
| Italian headers | | italian |

## What the ingestion engine must handle

1. Semicolon AND comma delimiters
2. Multiple date formats: DD.MM.YYYY, D.M.YYYY, YYYY-MM-DD, DD/MM/YYYY
3. Four number separator patterns: plain dot, space+comma, dot+comma, comma+dot
4. Multiple encodings: UTF-8, Windows-1252, Windows-1250, ISO-8859-1, ISO-8859-15
5. Czech, English, French, and Italian column headers (German, Spanish, and others in deterministic dictionary)
6. Customer name variants that should be fuzzy-matched (accents, legal suffixes, casing, abbreviations)
7. Missing fields (no email, no VAT, no company name)
8. Partial payments (amount due < total amount)
9. Already-paid invoices (amount due = 0)
10. Quoted fields containing the delimiter character
11. European legal suffixes: s.r.o., a.s. (CZ), SARL, SAS, SA, EURL, SCI (FR), S.r.l., S.p.A., S.a.s., S.n.c. (IT), GmbH, KG, AG (DE), SL, SA (ES), Ltd, LLP (UK)
