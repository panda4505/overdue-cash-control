export type ScopeType = "full_snapshot" | "partial" | "unknown";

export interface TargetFieldDefinition {
  targetField: string;
  label: string;
  required: boolean;
  group: "core" | "auxiliary";
}

export interface MappingSelection {
  target_field: string;
  source_column: string | null;
}

export interface PreviewColumnMapping {
  source_column: string;
  target_field: string;
  confidence: number;
  method: string;
  tier: string;
}

export interface PreviewMappingConflict {
  target_field: string;
  winner: string;
  loser: string;
  winner_confidence: number;
  loser_confidence: number;
}

export interface PreviewMappingResult {
  success: boolean;
  mappings: PreviewColumnMapping[];
  unmapped_source_columns: string[];
  unmapped_required_fields: string[];
  amount_fallback_active: boolean;
  conflicts: PreviewMappingConflict[];
  overall_confidence: number;
  method: string;
}

export interface ImportPreview {
  success: boolean;
  filename: string;
  file_hash: string;
  file_size_bytes: number;
  encoding: string | null;
  delimiter: string | null;
  date_format: string | null;
  decimal_separator: string | null;
  thousands_separator: string | null;
  total_rows: number;
  mapping: PreviewMappingResult | null;
  sample_rows: Array<Record<string, string | number | boolean | null>>;
  sheet_name: string | null;
  sheet_names: string[];
  method: string;
  warnings: string[];
  error: string | null;
}

export interface FuzzyMatchEntry {
  file_normalized_name: string;
  file_raw_name: string;
  existing_customer_id: string;
  existing_customer_name: string;
  score: number;
  match_type: string;
  confidence: string;
}

export interface FuzzyMatches {
  auto_merges: FuzzyMatchEntry[];
  candidates: FuzzyMatchEntry[];
}

export interface AppliedTemplate {
  id: string;
  name: string;
  scope_type: ScopeType;
  column_mapping: Record<string, string>;
  delimiter: string | null;
  decimal_separator: string | null;
  thousands_separator: string | null;
  encoding: string | null;
  date_format: string | null;
  times_used: number;
}

export interface UploadImportResponse {
  import_id: string | null;
  preview: ImportPreview;
  duplicate_warning: string | null;
  fuzzy_matches: FuzzyMatches | null;
  applied_template?: AppliedTemplate;
}

export interface SaveTemplateResponse {
  template: AppliedTemplate;
}

export const TARGET_FIELDS: TargetFieldDefinition[] = [
  {
    targetField: "invoice_number",
    label: "Invoice Number",
    required: true,
    group: "core",
  },
  {
    targetField: "customer_name",
    label: "Customer Name",
    required: true,
    group: "core",
  },
  {
    targetField: "due_date",
    label: "Due Date",
    required: true,
    group: "core",
  },
  {
    targetField: "outstanding_amount",
    label: "Outstanding Amount",
    required: true,
    group: "core",
  },
  {
    targetField: "gross_amount",
    label: "Gross Amount",
    required: false,
    group: "core",
  },
  {
    targetField: "issue_date",
    label: "Issue Date",
    required: false,
    group: "core",
  },
  {
    targetField: "currency",
    label: "Currency",
    required: false,
    group: "core",
  },
  {
    targetField: "vat_id",
    label: "VAT / Tax ID",
    required: false,
    group: "core",
  },
  {
    targetField: "company_id",
    label: "Company Registration Number",
    required: false,
    group: "core",
  },
  {
    targetField: "email",
    label: "Contact Email",
    required: false,
    group: "core",
  },
  {
    targetField: "phone",
    label: "Contact Phone",
    required: false,
    group: "core",
  },
  {
    targetField: "notes",
    label: "Notes",
    required: false,
    group: "core",
  },
  {
    targetField: "status",
    label: "Invoice Status",
    required: false,
    group: "auxiliary",
  },
  {
    targetField: "contact_name",
    label: "Contact Person",
    required: false,
    group: "auxiliary",
  },
];

export const SCOPE_OPTIONS: Array<{
  value: ScopeType;
  label: string;
  description: string;
}> = [
  {
    value: "full_snapshot",
    label: "Full snapshot",
    description: "This file contains all open invoices.",
  },
  {
    value: "partial",
    label: "Partial / filtered",
    description: "This file contains only some invoices.",
  },
  {
    value: "unknown",
    label: "Unknown",
    description: "Use this when you are not sure how complete the file is.",
  },
];

export const TOTAL_TARGET_FIELDS = TARGET_FIELDS.length;

export function buildInitialMappings(
  previewMappings: PreviewColumnMapping[],
): MappingSelection[] {
  const lookup = new Map(
    previewMappings.map((mapping) => [mapping.target_field, mapping.source_column]),
  );

  return TARGET_FIELDS.map((field) => ({
    target_field: field.targetField,
    source_column: lookup.get(field.targetField) ?? null,
  }));
}

export function buildMappingDict(
  mappings: Array<{ target_field: string; source_column: string | null }>,
): Record<string, string> {
  const dict: Record<string, string> = {};

  for (const mapping of mappings) {
    if (mapping.source_column) {
      dict[mapping.target_field] = mapping.source_column;
    }
  }

  return dict;
}

export function collectAvailableHeaders(preview: ImportPreview): string[] {
  const headers = new Set<string>();

  for (const row of preview.sample_rows) {
    for (const header of Object.keys(row)) {
      headers.add(header);
    }
  }

  for (const mapping of preview.mapping?.mappings ?? []) {
    headers.add(mapping.source_column);
  }

  for (const unmappedColumn of preview.mapping?.unmapped_source_columns ?? []) {
    headers.add(unmappedColumn);
  }

  return Array.from(headers);
}

export function getMappingValidationErrors(
  mappings: Array<{ target_field: string; source_column: string | null }>,
): string[] {
  const dict = buildMappingDict(mappings);
  const errors: string[] = [];

  if (!dict.invoice_number) {
    errors.push("Invoice Number is required.");
  }

  if (!dict.customer_name) {
    errors.push("Customer Name is required.");
  }

  if (!dict.due_date) {
    errors.push("Due Date is required.");
  }

  if (!dict.outstanding_amount && !dict.gross_amount) {
    errors.push("Map Outstanding Amount or Gross Amount before continuing.");
  }

  const sourceToTargets = new Map<string, string[]>();

  for (const mapping of mappings) {
    if (!mapping.source_column) {
      continue;
    }

    const targets = sourceToTargets.get(mapping.source_column) ?? [];
    targets.push(mapping.target_field);
    sourceToTargets.set(mapping.source_column, targets);
  }

  for (const [sourceColumn, targets] of Array.from(sourceToTargets.entries())) {
    if (targets.length > 1) {
      errors.push(`Source column "${sourceColumn}" is assigned more than once.`);
    }
  }

  return errors;
}
