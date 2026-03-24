"use client";

import type {
  ChangeEvent,
  DragEvent,
  FormEvent,
} from "react";
import { useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
  ChevronDown,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  Mail,
  UploadCloud,
} from "lucide-react";
import { toast } from "sonner";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/contexts/auth-context";
import { apiFetch } from "@/lib/api";
import {
  SCOPE_OPTIONS,
  TARGET_FIELDS,
  buildInitialMappings,
  buildMappingDict,
  collectAvailableHeaders,
  getMappingValidationErrors,
  type MappingSelection,
  type PreviewDiffResponse,
  type PreviewColumnMapping,
  type SaveTemplateResponse,
  type ScopeType,
  type UploadImportResponse,
} from "@/lib/imports";
import { cn } from "@/lib/utils";

const UNMAPPED_VALUE = "__unmapped__";

type Step = 1 | 2 | 3 | 4;

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatCellValue(value: string | number | boolean | null) {
  if (value === null || value === "") {
    return "—";
  }

  return String(value);
}

function formatScopeLabel(scopeType: ScopeType) {
  return SCOPE_OPTIONS.find((option) => option.value === scopeType)?.label ?? scopeType;
}

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function getConfidenceText(mapping: PreviewColumnMapping) {
  return `${mapping.method} • ${formatPercent(mapping.confidence)}`;
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat("en", {
    style: "currency",
    currency: "EUR",
  }).format(amount);
}

function formatPreviewValue(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  return String(value);
}

function formatAnomalyDescription(
  anomalyType: string,
  details: Record<string, unknown>,
) {
  if (anomalyType === "balance_increase") {
    return `Balance ${formatPreviewValue(details.previous_amount as number | null)} -> ${formatPreviewValue(details.new_amount as number | null)} (+${formatPreviewValue(details.increase as number | null)})`;
  }

  if (anomalyType === "due_date_change") {
    return `Due date ${formatPreviewValue(details.previous_due_date as string | null)} -> ${formatPreviewValue(details.new_due_date as string | null)}`;
  }

  if (anomalyType === "reappearance") {
    return `Previously ${formatPreviewValue(details.previous_status as string | null)}, restored to ${formatPreviewValue(details.restored_to as string | null)}`;
  }

  if (anomalyType === "overdue_spike") {
    return `Overdue invoices ${formatPreviewValue(details.previous_overdue_count as number | null)} -> ${formatPreviewValue(details.new_overdue_count as number | null)} (delta ${formatPreviewValue(details.delta as number | null)})`;
  }

  if (anomalyType === "cluster_risk") {
    return `${formatPreviewValue(details.overdue_invoice_count as number | null)} overdue invoices after import`;
  }

  return "Requires review.";
}

export default function NewImportPage() {
  const { account, refreshAccount } = useAuth();
  const router = useRouter();
  const fileInputId = useId();

  const [step, setStep] = useState<Step>(1);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadImportResponse | null>(null);
  const [mappings, setMappings] = useState<MappingSelection[]>([]);
  const [scopeType, setScopeType] = useState<ScopeType>("unknown");
  const [mergeDecisions, setMergeDecisions] = useState<Record<string, string>>({});
  const [savedTemplateName, setSavedTemplateName] = useState<string | null>(null);
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [isSavingTemplate, setIsSavingTemplate] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [previewDiff, setPreviewDiff] = useState<PreviewDiffResponse | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const preview = uploadResult?.preview ?? null;
  const previewMapping = preview?.mapping ?? null;
  const availableHeaders = preview ? collectAvailableHeaders(preview) : [];
  const previewMappingLookup = new Map(
    (previewMapping?.mappings ?? []).map((mapping) => [mapping.target_field, mapping]),
  );
  const mappingDict = buildMappingDict(mappings);
  const mappingValidationErrors = getMappingValidationErrors(mappings);
  const isMappingValid = mappingValidationErrors.length === 0;
  const amountRuleSatisfied =
    Boolean(mappingDict.outstanding_amount) || Boolean(mappingDict.gross_amount);
  const fuzzyMatches = uploadResult?.fuzzy_matches ?? null;
  const autoMerges = fuzzyMatches?.auto_merges ?? [];
  const candidates = fuzzyMatches?.candidates ?? [];
  const mergeDetailByFileName = new Map(
    (previewDiff?.customers_merged_detail ?? []).map((merge) => [
      merge.file_name,
      merge.match_type,
    ]),
  );

  const resetPreviewState = () => {
    setUploadResult(null);
    setMappings([]);
    setMergeDecisions({});
    setSavedTemplateName(null);
    setShowTemplateForm(false);
    setTemplateName("");
    setPreviewDiff(null);
    setPreviewError(null);
    setExpandedSections(new Set());
  };

  const toggleSection = (key: string) => {
    setExpandedSections((previous) => {
      const next = new Set(previous);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleFileSelection = (file: File | null) => {
    setSelectedFile(file);
    setUploadError(null);
  };

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFileSelection(event.target.files?.[0] ?? null);
  };

  const handleDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    handleFileSelection(event.dataTransfer.files?.[0] ?? null);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadError("Select a CSV, TSV, or XLSX file first.");
      return;
    }

    if (!account) {
      setUploadError("Account details are still loading.");
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const result = await apiFetch<UploadImportResponse>(
        `/accounts/${account.id}/imports/upload`,
        {
          method: "POST",
          body: formData,
        },
      );

      if (result.import_id === null) {
        const message = result.preview.error ?? "The file could not be parsed.";
        resetPreviewState();
        setStep(1);
        setUploadError(message);
        toast.error(message);
        return;
      }

      if (!result.preview.mapping) {
        const message = "No mapping preview was returned for this upload.";
        resetPreviewState();
        setStep(1);
        setUploadError(message);
        toast.error(message);
        return;
      }

      setUploadResult(result);
      setMappings(buildInitialMappings(result.preview.mapping.mappings));
      setScopeType("unknown");
      setMergeDecisions({});
      setSavedTemplateName(result.applied_template?.name ?? null);
      setTemplateName(result.applied_template?.name ?? "");
      setShowTemplateForm(false);
      setPreviewDiff(null);
      setPreviewError(null);
      setExpandedSections(new Set());
      setStep(2);
      toast.success("Import preview ready");
    } catch (error) {
      const message = getErrorMessage(error, "Unable to upload this file.");
      resetPreviewState();
      setStep(1);
      setUploadError(message);
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleMappingChange = (targetField: string, nextValue: string | null) => {
    setMappings((currentMappings) =>
      currentMappings.map((mapping) =>
        mapping.target_field === targetField
          ? {
              ...mapping,
              source_column:
                nextValue === null || nextValue === UNMAPPED_VALUE ? null : nextValue,
            }
          : mapping,
      ),
    );
  };

  const handleContinueFromMapping = () => {
    if (!isMappingValid) {
      return;
    }

    setStep(candidates.length > 0 ? 3 : 4);
  };

  const handleCandidateDecision = (
    normalizedName: string,
    customerId: string,
    shouldMerge: boolean,
  ) => {
    setMergeDecisions((currentDecisions) => {
      if (!shouldMerge) {
        const nextDecisions = { ...currentDecisions };
        delete nextDecisions[normalizedName];
        return nextDecisions;
      }

      return {
        ...currentDecisions,
        [normalizedName]: customerId,
      };
    });
  };

  const handleSaveTemplate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!uploadResult?.import_id || !preview || !isMappingValid) {
      return;
    }

    if (!templateName.trim()) {
      toast.error("Enter a template name first.");
      return;
    }

    setIsSavingTemplate(true);

    try {
      const response = await apiFetch<SaveTemplateResponse>(
        `/imports/${uploadResult.import_id}/save-template`,
        {
          method: "POST",
          body: JSON.stringify({
            name: templateName.trim(),
            mapping: buildMappingDict(mappings),
            scope_type: scopeType,
            delimiter: preview.delimiter,
            decimal_separator: preview.decimal_separator,
            thousands_separator: preview.thousands_separator,
            encoding: preview.encoding,
            date_format: preview.date_format,
          }),
        },
      );

      setSavedTemplateName(response.template.name);
      setTemplateName(response.template.name);
      setShowTemplateForm(false);
      toast.success("Template saved");
    } catch (error) {
      toast.error(getErrorMessage(error, "Unable to save template."));
    } finally {
      setIsSavingTemplate(false);
    }
  };

  const fetchPreviewDiff = async () => {
    if (!uploadResult?.import_id || !isMappingValid) {
      return;
    }

    setIsLoadingPreview(true);
    setPreviewError(null);
    setPreviewDiff(null);
    setExpandedSections(new Set());

    try {
      const result = await apiFetch<PreviewDiffResponse>(
        `/imports/${uploadResult.import_id}/preview-diff`,
        {
          method: "POST",
          body: JSON.stringify({
            mapping: buildMappingDict(mappings),
            scope_type: scopeType,
            merge_decisions: candidates.length > 0 ? mergeDecisions : null,
          }),
        },
      );
      setPreviewDiff(result);
    } catch (error) {
      const message = getErrorMessage(error, "Unable to generate import preview.");
      setPreviewError(message);
      toast.error(message);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!uploadResult?.import_id || !isMappingValid) {
      return;
    }

    setIsConfirming(true);

    try {
      await apiFetch<Record<string, unknown>>(
        `/imports/${uploadResult.import_id}/confirm`,
        {
          method: "POST",
          body: JSON.stringify({
            mapping: buildMappingDict(mappings),
            scope_type: scopeType,
            merge_decisions: candidates.length > 0 ? mergeDecisions : null,
          }),
        },
      );

      await refreshAccount();
      toast.success("Import confirmed");
      router.replace("/dashboard");
    } catch (error) {
      toast.error(getErrorMessage(error, "Unable to confirm import."));
    } finally {
      setIsConfirming(false);
    }
  };

  useEffect(() => {
    if (step === 4 && previewDiff === null && !isLoadingPreview) {
      void fetchPreviewDiff();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  if (!account) {
    return <p className="text-sm text-muted-foreground">Loading account...</p>;
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6">
      <section className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
          New Import
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">Bring in a receivables file</h1>
        <p className="max-w-3xl text-muted-foreground">
          Upload a file, confirm the mapping, review customer merge suggestions,
          and finalize the import when everything looks right.
        </p>
      </section>

      <div className="grid gap-3 md:grid-cols-4">
        {[
          { stepNumber: 1, label: "Upload" },
          { stepNumber: 2, label: "Mapping" },
          { stepNumber: 3, label: "Fuzzy Match" },
          { stepNumber: 4, label: "Review Changes" },
        ].map((item) => {
          const isActive = step === item.stepNumber;
          const isComplete = step > item.stepNumber;

          return (
            <div
              key={item.stepNumber}
              className={cn(
                "rounded-xl border bg-background/90 p-4 shadow-sm transition-colors",
                isActive && "border-foreground/30 bg-foreground/[0.02]",
                isComplete && "border-green-200 bg-green-50/70",
              )}
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "flex size-8 items-center justify-center rounded-full border text-sm font-medium",
                    isComplete
                      ? "border-green-300 bg-green-100 text-green-700"
                      : isActive
                        ? "border-foreground/30 bg-foreground text-background"
                        : "border-border text-muted-foreground",
                  )}
                >
                  {isComplete ? <CheckCircle2 className="size-4" /> : item.stepNumber}
                </div>
                <div>
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {isComplete ? "Done" : isActive ? "Current step" : "Upcoming"}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {step === 1 ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="bg-background/90">
            <CardHeader className="space-y-3">
              <Mail className="size-5 text-foreground" />
              <div className="space-y-1">
                <CardTitle>Email Ingestion</CardTitle>
                <CardDescription>
                  Forward invoices into your account when the inbound mailbox is
                  configured.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {account.resend_inbound_address ? (
                <div className="rounded-lg border bg-muted/30 p-4">
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                    Inbound address
                  </p>
                  <p className="mt-2 break-all font-medium text-foreground">
                    {account.resend_inbound_address}
                  </p>
                </div>
              ) : (
                <p className="text-sm leading-6 text-muted-foreground">
                  Email ingestion not configured yet.
                </p>
              )}
            </CardContent>
          </Card>

          <Card className="bg-background/90">
            <CardHeader className="space-y-3">
              <UploadCloud className="size-5 text-foreground" />
              <div className="space-y-1">
                <CardTitle>Manual Upload</CardTitle>
                <CardDescription>
                  CSV, TSV, and XLSX files are supported in this milestone.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <input
                id={fileInputId}
                type="file"
                accept=".csv,.tsv,.xlsx"
                className="hidden"
                onChange={handleFileInputChange}
              />
              <label
                htmlFor={fileInputId}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-6 py-12 text-center transition-colors",
                  isDragging
                    ? "border-foreground bg-muted/40"
                    : "border-border hover:border-foreground/30 hover:bg-muted/20",
                )}
              >
                <FileSpreadsheet className="mb-3 size-10 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">
                  Drag and drop a file here
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  or click to browse your computer
                </p>
                <p className="mt-3 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                  CSV / TSV / XLSX
                </p>
              </label>

              {selectedFile ? (
                <div className="rounded-lg border bg-muted/30 p-3">
                  <p className="text-sm font-medium text-foreground">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatBytes(selectedFile.size)}
                  </p>
                </div>
              ) : null}

              {uploadError ? (
                <Alert variant="destructive">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Upload failed</AlertTitle>
                  <AlertDescription>{uploadError}</AlertDescription>
                </Alert>
              ) : null}

              <Button
                type="button"
                size="lg"
                className="w-full"
                disabled={!selectedFile || isUploading}
                onClick={handleUpload}
              >
                {isUploading ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  "Upload file"
                )}
              </Button>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {step === 2 && preview && previewMapping ? (
        <div className="space-y-6">
          {uploadResult?.applied_template ? (
            <Alert>
              <AlertTitle>
                Template "{uploadResult.applied_template.name}" was auto-applied.
              </AlertTitle>
              <AlertDescription>
                Review the suggested mapping below before continuing.
              </AlertDescription>
            </Alert>
          ) : null}

          {uploadResult?.duplicate_warning ? (
            <Alert>
              <AlertTitle>Duplicate warning</AlertTitle>
              <AlertDescription>{uploadResult.duplicate_warning}</AlertDescription>
            </Alert>
          ) : null}

          {preview.warnings.length > 0 ? (
            <Alert>
              <AlertTitle>Preview warnings</AlertTitle>
              <AlertDescription>{preview.warnings.join(" ")}</AlertDescription>
            </Alert>
          ) : null}

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
            <Card className="bg-background/90">
              <CardHeader>
                <CardTitle>Sample rows</CardTitle>
                <CardDescription>
                  Reviewing the first few parsed rows makes it easier to confirm
                  the inferred headers.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {availableHeaders.length > 0 ? (
                  <div className="overflow-x-auto rounded-lg border">
                    <table className="min-w-full border-collapse text-left text-sm">
                      <thead className="bg-muted/40">
                        <tr>
                          {availableHeaders.map((header) => (
                            <th
                              key={header}
                              className="border-b px-3 py-2 font-medium text-foreground"
                            >
                              {header}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.sample_rows.slice(0, 6).map((row, index) => (
                          <tr key={index} className="border-b last:border-b-0">
                            {availableHeaders.map((header) => (
                              <td
                                key={`${index}-${header}`}
                                className="max-w-[220px] px-3 py-2 text-muted-foreground"
                              >
                                {formatCellValue(row[header] ?? null)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No sample rows were returned for this file.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card className="bg-background/90">
              <CardHeader>
                <CardTitle>Column Mapping Confirmation</CardTitle>
                <CardDescription>
                  Confirm how each backend field should map to the uploaded file.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {(["core", "auxiliary"] as const).map((group) => (
                  <div key={group} className="space-y-3">
                    <div>
                      <h2 className="text-sm font-semibold text-foreground">
                        {group === "core" ? "Core fields" : "Auxiliary fields"}
                      </h2>
                      <p className="text-xs text-muted-foreground">
                        {group === "core"
                          ? "Stored in the database for the import."
                          : "Shown in preview only for v1."}
                      </p>
                    </div>

                    <div className="space-y-3">
                      {TARGET_FIELDS.filter((field) => field.group === group).map((field) => {
                        const currentMapping = mappings.find(
                          (mapping) => mapping.target_field === field.targetField,
                        );
                        const initialMapping = previewMappingLookup.get(field.targetField);
                        const showConfidence =
                          initialMapping &&
                          currentMapping?.source_column === initialMapping.source_column;
                        const showRequiredError =
                          field.targetField === "outstanding_amount"
                            ? !amountRuleSatisfied
                            : field.required && !currentMapping?.source_column;

                        return (
                          <div
                            key={field.targetField}
                            className="grid gap-3 rounded-xl border p-3 md:grid-cols-[minmax(0,180px)_1fr] md:items-center"
                          >
                            <div className="space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-medium text-foreground">
                                  {field.label}
                                </p>
                                {showConfidence ? (
                                  <Badge variant="outline">
                                    {getConfidenceText(initialMapping)}
                                  </Badge>
                                ) : null}
                                {showRequiredError ? (
                                  <Badge variant="destructive">Required</Badge>
                                ) : null}
                              </div>
                              <p className="text-xs text-muted-foreground">
                                {field.targetField}
                              </p>
                            </div>

                            <Select
                              value={currentMapping?.source_column ?? UNMAPPED_VALUE}
                              onValueChange={(nextValue) =>
                                handleMappingChange(field.targetField, nextValue)
                              }
                            >
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder="Choose a source column" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={UNMAPPED_VALUE}>— Unmapped —</SelectItem>
                                {availableHeaders.map((header) => (
                                  <SelectItem key={header} value={header}>
                                    {header}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}

                {previewMapping.unmapped_source_columns.length > 0 ? (
                  <p className="text-sm text-muted-foreground">
                    These source columns were not mapped:{" "}
                    {previewMapping.unmapped_source_columns.join(", ")}.
                  </p>
                ) : null}

                {previewMapping.unmapped_required_fields.length > 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Backend preview still flagged these required fields as
                    unresolved: {previewMapping.unmapped_required_fields.join(", ")}.
                  </p>
                ) : null}

                {previewMapping.amount_fallback_active ? (
                  <Alert>
                    <AlertTitle>Amount fallback is active</AlertTitle>
                    <AlertDescription>
                      Gross Amount will be used when Outstanding Amount is not
                      present in the source file.
                    </AlertDescription>
                  </Alert>
                ) : null}

                {previewMapping.conflicts.length > 0 ? (
                  <Alert>
                    <AlertTitle>Mapping conflicts detected</AlertTitle>
                    <AlertDescription className="space-y-2">
                      {previewMapping.conflicts.map((conflict, index) => (
                        <p key={`${conflict.target_field}-${index}`}>
                          {conflict.target_field}: kept "{conflict.winner}" (
                          {formatPercent(conflict.winner_confidence)}) over "
                          {conflict.loser}" ({formatPercent(conflict.loser_confidence)}).
                        </p>
                      ))}
                    </AlertDescription>
                  </Alert>
                ) : null}

                <div className="space-y-3">
                  <div>
                    <Label className="text-sm font-semibold text-foreground">
                      Scope type
                    </Label>
                    <p className="mt-1 text-xs text-muted-foreground">
                      This controls how the backend treats disappearances in the
                      import history.
                    </p>
                  </div>
                  <div className="grid gap-3">
                    {SCOPE_OPTIONS.map((option) => (
                      <label
                        key={option.value}
                        className={cn(
                          "cursor-pointer rounded-xl border p-4 transition-colors",
                          scopeType === option.value
                            ? "border-foreground/30 bg-muted/40"
                            : "border-border hover:border-foreground/20 hover:bg-muted/20",
                        )}
                      >
                        <input
                          type="radio"
                          name="scope-type"
                          value={option.value}
                          checked={scopeType === option.value}
                          onChange={() => setScopeType(option.value)}
                          className="sr-only"
                        />
                        <p className="text-sm font-medium text-foreground">
                          {option.label}
                        </p>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {option.description}
                        </p>
                      </label>
                    ))}
                  </div>
                </div>

                {!isMappingValid ? (
                  <Alert variant="destructive">
                    <AlertTitle>Fix mapping validation before continuing</AlertTitle>
                    <AlertDescription className="space-y-2">
                      {mappingValidationErrors.map((message) => (
                        <p key={message}>{message}</p>
                      ))}
                    </AlertDescription>
                  </Alert>
                ) : null}
              </CardContent>
              <CardFooter className="flex flex-col gap-3 sm:flex-row sm:justify-between">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setStep(1)}
                >
                  Choose another file
                </Button>
                <Button
                  type="button"
                  size="lg"
                  disabled={!isMappingValid}
                  onClick={handleContinueFromMapping}
                >
                  {candidates.length > 0 ? "Continue to fuzzy match review" : "Continue to review"}
                  <ArrowRight className="size-4" />
                </Button>
              </CardFooter>
            </Card>
          </div>
        </div>
      ) : null}

      {step === 3 && preview && previewMapping ? (
        <div className="space-y-6">
          <Card className="bg-background/90">
            <CardHeader>
              <CardTitle>Fuzzy Match Decisions</CardTitle>
              <CardDescription>
                Review customer suggestions before the import is confirmed.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {autoMerges.length > 0 ? (
                <div className="space-y-3 rounded-xl border bg-muted/20 p-4">
                  <div>
                    <h2 className="text-sm font-semibold text-foreground">
                      These customers will be automatically matched
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      No action is needed for the high-confidence matches below.
                    </p>
                  </div>
                  <div className="space-y-2">
                    {autoMerges.map((match) => (
                      <div
                        key={`${match.file_normalized_name}-${match.existing_customer_id}`}
                        className="rounded-lg border bg-background/80 p-3"
                      >
                        <p className="text-sm font-medium text-foreground">
                          {match.file_raw_name} → {match.existing_customer_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatPercent(match.score)} • {match.match_type} •{" "}
                          {match.confidence}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="space-y-4">
                {candidates.map((candidate) => {
                  const shouldMerge =
                    mergeDecisions[candidate.file_normalized_name] ===
                    candidate.existing_customer_id;

                  return (
                    <Card
                      key={`${candidate.file_normalized_name}-${candidate.existing_customer_id}`}
                      className="border-border/80 bg-muted/10"
                    >
                      <CardHeader>
                        <CardTitle className="text-base">
                          {candidate.file_raw_name}
                        </CardTitle>
                        <CardDescription>
                          Suggested match: {candidate.existing_customer_name}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="rounded-lg border bg-background/80 p-3 text-sm text-muted-foreground">
                          Score {formatPercent(candidate.score)} via {candidate.match_type} (
                          {candidate.confidence} confidence)
                        </div>

                        <div className="grid gap-3 md:grid-cols-2">
                          <label
                            className={cn(
                              "cursor-pointer rounded-xl border p-4 transition-colors",
                              !shouldMerge
                                ? "border-foreground/30 bg-background"
                                : "border-border bg-background/70 hover:border-foreground/20",
                            )}
                          >
                            <input
                              type="radio"
                              name={`merge-${candidate.file_normalized_name}`}
                              checked={!shouldMerge}
                              onChange={() =>
                                handleCandidateDecision(
                                  candidate.file_normalized_name,
                                  candidate.existing_customer_id,
                                  false,
                                )
                              }
                              className="sr-only"
                            />
                            <p className="text-sm font-medium text-foreground">
                              Keep as new customer
                            </p>
                            <p className="mt-1 text-sm text-muted-foreground">
                              Default conservative option for this file customer.
                            </p>
                          </label>

                          <label
                            className={cn(
                              "cursor-pointer rounded-xl border p-4 transition-colors",
                              shouldMerge
                                ? "border-foreground/30 bg-background"
                                : "border-border bg-background/70 hover:border-foreground/20",
                            )}
                          >
                            <input
                              type="radio"
                              name={`merge-${candidate.file_normalized_name}`}
                              checked={shouldMerge}
                              onChange={() =>
                                handleCandidateDecision(
                                  candidate.file_normalized_name,
                                  candidate.existing_customer_id,
                                  true,
                                )
                              }
                              className="sr-only"
                            />
                            <p className="text-sm font-medium text-foreground">
                              Merge into {candidate.existing_customer_name}
                            </p>
                            <p className="mt-1 text-sm text-muted-foreground">
                              Use the suggested existing customer record.
                            </p>
                          </label>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
            <CardFooter className="flex flex-col gap-3 sm:flex-row sm:justify-between">
              <Button type="button" variant="outline" onClick={() => setStep(2)}>
                Back to mapping
              </Button>
              <Button type="button" size="lg" onClick={() => setStep(4)}>
                Continue to review
                <ArrowRight className="size-4" />
              </Button>
            </CardFooter>
          </Card>
        </div>
      ) : null}

      {step === 4 && preview && previewMapping ? (
        <div className="space-y-6">
          {isLoadingPreview ? (
            <Card className="bg-background/90">
              <CardHeader className="space-y-4">
                <div className="flex items-center gap-3">
                  <Loader2 className="size-5 animate-spin text-muted-foreground" />
                  <div>
                    <CardTitle>Analyzing import...</CardTitle>
                    <CardDescription>
                      Building the business diff preview for this file.
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 md:grid-cols-5">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <div
                      key={index}
                      className="space-y-3 rounded-xl border bg-muted/10 p-4 animate-pulse"
                    >
                      <div className="h-3 w-24 rounded bg-muted" />
                      <div className="h-8 w-16 rounded bg-muted" />
                      <div className="h-3 w-20 rounded bg-muted" />
                    </div>
                  ))}
                </div>
                <div className="space-y-3 rounded-xl border p-4 animate-pulse">
                  <div className="h-4 w-40 rounded bg-muted" />
                  <div className="h-24 w-full rounded bg-muted/70" />
                </div>
                <div className="space-y-3 rounded-xl border p-4 animate-pulse">
                  <div className="h-4 w-48 rounded bg-muted" />
                  <div className="h-20 w-full rounded bg-muted/70" />
                </div>
              </CardContent>
            </Card>
          ) : null}

          {!isLoadingPreview && previewError ? (
            <Alert variant="destructive">
              <AlertCircle className="size-4" />
              <AlertTitle>Unable to generate import preview</AlertTitle>
              <AlertDescription className="space-y-4">
                <p>{previewError}</p>
                <Button type="button" variant="outline" onClick={fetchPreviewDiff}>
                  Retry
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          {!isLoadingPreview && previewDiff ? (
            <>
              {uploadResult?.duplicate_warning ? (
                <Alert className="border-amber-200 bg-amber-50/70 text-amber-950 [&>svg]:text-amber-600">
                  <AlertCircle className="size-4" />
                  <AlertTitle>Duplicate warning</AlertTitle>
                  <AlertDescription>{uploadResult.duplicate_warning}</AlertDescription>
                </Alert>
              ) : null}

              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <Card className="bg-background/90">
                  <CardHeader className="space-y-1 pb-2">
                    <CardDescription>New invoices</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p
                      className={cn(
                        "text-3xl font-semibold tracking-tight",
                        previewDiff.invoices_created > 0
                          ? "text-emerald-600"
                          : "text-foreground",
                      )}
                    >
                      {previewDiff.invoices_created}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {formatCurrency(previewDiff.total_new_amount)}
                    </p>
                  </CardContent>
                </Card>

                <Card className="bg-background/90">
                  <CardHeader className="space-y-1 pb-2">
                    <CardDescription>Updated</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p
                      className={cn(
                        "text-3xl font-semibold tracking-tight",
                        previewDiff.invoices_updated > 0
                          ? "text-amber-600"
                          : "text-foreground",
                      )}
                    >
                      {previewDiff.invoices_updated}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Changed invoice records
                    </p>
                  </CardContent>
                </Card>

                {scopeType === "full_snapshot" ? (
                  <Card className="bg-background/90">
                    <CardHeader className="space-y-1 pb-2">
                      <CardDescription>No longer in file</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-1">
                      <p
                        className={cn(
                          "text-3xl font-semibold tracking-tight",
                          previewDiff.invoices_disappeared > 0
                            ? "text-orange-600"
                            : "text-foreground",
                        )}
                      >
                        {previewDiff.invoices_disappeared}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {formatCurrency(previewDiff.total_disappeared_amount)}
                      </p>
                    </CardContent>
                  </Card>
                ) : null}

                <Card className="bg-background/90">
                  <CardHeader className="space-y-1 pb-2">
                    <CardDescription>Anomalies</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-3xl font-semibold tracking-tight">
                      {previewDiff.anomalies_flagged}
                    </p>
                    {previewDiff.anomalies_flagged > 0 ? (
                      <Badge
                        variant="secondary"
                        className="bg-amber-100 text-amber-800"
                      >
                        Review flagged items
                      </Badge>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No anomalies flagged
                      </p>
                    )}
                  </CardContent>
                </Card>

                <Card className="bg-background/90">
                  <CardHeader className="space-y-1 pb-2">
                    <CardDescription>Unchanged</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p className="text-3xl font-semibold tracking-tight text-muted-foreground">
                      {previewDiff.invoices_unchanged}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      No business changes
                    </p>
                  </CardContent>
                </Card>
              </div>

              <div className="space-y-4">
                {previewDiff.invoices_created > 0 ? (
                  <Card className="bg-background/90">
                    <CardHeader className="pb-3">
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 text-left"
                        onClick={() => toggleSection("created")}
                      >
                        <div>
                          <CardTitle>New invoices ({previewDiff.invoices_created})</CardTitle>
                          <CardDescription>
                            Invoices that will be created on confirm.
                          </CardDescription>
                        </div>
                        <ChevronDown
                          className={cn(
                            "size-4 transition-transform",
                            expandedSections.has("created") && "rotate-180",
                          )}
                        />
                      </button>
                    </CardHeader>
                    {expandedSections.has("created") ? (
                      <CardContent>
                        <div className="overflow-x-auto rounded-lg border">
                          <table className="min-w-full border-collapse text-left text-sm">
                            <thead className="bg-muted/40">
                              <tr>
                                <th className="border-b px-3 py-2 font-medium">Invoice #</th>
                                <th className="border-b px-3 py-2 font-medium">Customer</th>
                                <th className="border-b px-3 py-2 font-medium">Amount</th>
                                <th className="border-b px-3 py-2 font-medium">Due Date</th>
                                <th className="border-b px-3 py-2 font-medium">Currency</th>
                              </tr>
                            </thead>
                            <tbody>
                              {previewDiff.created_invoices.map((invoice) => (
                                <tr
                                  key={`${invoice.invoice_number}-${invoice.customer_name}`}
                                  className="border-b last:border-b-0"
                                >
                                  <td className="px-3 py-2">{invoice.invoice_number}</td>
                                  <td className="px-3 py-2 text-muted-foreground">
                                    {invoice.customer_name}
                                  </td>
                                  <td className="px-3 py-2">
                                    {formatCurrency(invoice.outstanding_amount)}
                                  </td>
                                  <td className="px-3 py-2 text-muted-foreground">
                                    {invoice.due_date}
                                  </td>
                                  <td className="px-3 py-2 text-muted-foreground">
                                    {invoice.currency}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    ) : null}
                  </Card>
                ) : null}

                {previewDiff.invoices_updated > 0 ? (
                  <Card className="bg-background/90">
                    <CardHeader className="pb-3">
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 text-left"
                        onClick={() => toggleSection("updated")}
                      >
                        <div>
                          <CardTitle>Updated invoices ({previewDiff.invoices_updated})</CardTitle>
                          <CardDescription>
                            Existing invoices with detected business changes.
                          </CardDescription>
                        </div>
                        <ChevronDown
                          className={cn(
                            "size-4 transition-transform",
                            expandedSections.has("updated") && "rotate-180",
                          )}
                        />
                      </button>
                    </CardHeader>
                    {expandedSections.has("updated") ? (
                      <CardContent>
                        <div className="overflow-x-auto rounded-lg border">
                          <table className="min-w-full border-collapse text-left text-sm">
                            <thead className="bg-muted/40">
                              <tr>
                                <th className="border-b px-3 py-2 font-medium">Invoice #</th>
                                <th className="border-b px-3 py-2 font-medium">Customer</th>
                                <th className="border-b px-3 py-2 font-medium">Changes</th>
                              </tr>
                            </thead>
                            <tbody>
                              {previewDiff.updated_invoices.map((invoice) => (
                                <tr
                                  key={`${invoice.invoice_number}-${invoice.customer_name}`}
                                  className="border-b align-top last:border-b-0"
                                >
                                  <td className="px-3 py-2">{invoice.invoice_number}</td>
                                  <td className="px-3 py-2 text-muted-foreground">
                                    {invoice.customer_name}
                                  </td>
                                  <td className="space-y-1 px-3 py-2 text-sm text-muted-foreground">
                                    {Object.entries(invoice.changes).map(
                                      ([fieldName, change]) => (
                                        <div key={fieldName}>
                                          {fieldName}: {formatPreviewValue(change.before)}{" -> "}
                                          {formatPreviewValue(change.after)}
                                        </div>
                                      ),
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    ) : null}
                  </Card>
                ) : null}

                {previewDiff.invoices_disappeared > 0 && scopeType === "full_snapshot" ? (
                  <Card className="bg-background/90">
                    <CardHeader className="pb-3">
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 text-left"
                        onClick={() => toggleSection("disappeared")}
                      >
                        <div>
                          <CardTitle>
                            No longer in file ({previewDiff.invoices_disappeared})
                          </CardTitle>
                          <CardDescription>
                            Open invoices that would be marked as possibly paid.
                          </CardDescription>
                        </div>
                        <ChevronDown
                          className={cn(
                            "size-4 transition-transform",
                            expandedSections.has("disappeared") && "rotate-180",
                          )}
                        />
                      </button>
                    </CardHeader>
                    {expandedSections.has("disappeared") ? (
                      <CardContent>
                        <div className="overflow-x-auto rounded-lg border">
                          <table className="min-w-full border-collapse text-left text-sm">
                            <thead className="bg-muted/40">
                              <tr>
                                <th className="border-b px-3 py-2 font-medium">Invoice #</th>
                                <th className="border-b px-3 py-2 font-medium">Customer</th>
                                <th className="border-b px-3 py-2 font-medium">Outstanding</th>
                                <th className="border-b px-3 py-2 font-medium">Days Overdue</th>
                              </tr>
                            </thead>
                            <tbody>
                              {previewDiff.disappeared_invoices.map((invoice) => (
                                <tr
                                  key={`${invoice.invoice_number}-${invoice.customer_name}`}
                                  className="border-b last:border-b-0"
                                >
                                  <td className="px-3 py-2">{invoice.invoice_number}</td>
                                  <td className="px-3 py-2 text-muted-foreground">
                                    {invoice.customer_name}
                                  </td>
                                  <td className="px-3 py-2">
                                    {formatCurrency(invoice.outstanding_amount)}
                                  </td>
                                  <td className="px-3 py-2 text-muted-foreground">
                                    {invoice.days_overdue}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </CardContent>
                    ) : null}
                  </Card>
                ) : null}

                {previewDiff.anomalies_flagged > 0 ? (
                  <Card className="bg-background/90">
                    <CardHeader className="pb-3">
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-3 text-left"
                        onClick={() => toggleSection("anomalies")}
                      >
                        <div>
                          <CardTitle>Anomalies ({previewDiff.anomalies_flagged})</CardTitle>
                          <CardDescription>
                            Differential risk signals detected from this import.
                          </CardDescription>
                        </div>
                        <ChevronDown
                          className={cn(
                            "size-4 transition-transform",
                            expandedSections.has("anomalies") && "rotate-180",
                          )}
                        />
                      </button>
                    </CardHeader>
                    {expandedSections.has("anomalies") ? (
                      <CardContent className="space-y-3">
                        {previewDiff.anomalies.map((anomaly, index) => (
                          <div
                            key={`${anomaly.anomaly_type}-${anomaly.invoice_number ?? anomaly.customer_name ?? index}`}
                            className="rounded-xl border bg-muted/10 p-4"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge variant="secondary">{anomaly.anomaly_type}</Badge>
                              {anomaly.invoice_number ? (
                                <span className="text-sm font-medium">
                                  {anomaly.invoice_number}
                                </span>
                              ) : null}
                              {!anomaly.invoice_number && anomaly.customer_name ? (
                                <span className="text-sm font-medium">
                                  {anomaly.customer_name}
                                </span>
                              ) : null}
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">
                              {formatAnomalyDescription(
                                anomaly.anomaly_type,
                                anomaly.details,
                              )}
                            </p>
                          </div>
                        ))}
                      </CardContent>
                    ) : null}
                  </Card>
                ) : null}

                <Card className="bg-background/90">
                  <CardHeader className="pb-3">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-3 text-left"
                      onClick={() => toggleSection("customers")}
                    >
                      <div>
                        <CardTitle>
                          Customer resolution ({previewDiff.customer_resolutions.length} customers)
                        </CardTitle>
                        <CardDescription>
                          How file customers map to existing or new records.
                        </CardDescription>
                      </div>
                      <ChevronDown
                        className={cn(
                          "size-4 transition-transform",
                          expandedSections.has("customers") && "rotate-180",
                        )}
                      />
                    </button>
                  </CardHeader>
                  {expandedSections.has("customers") ? (
                    <CardContent>
                      <div className="overflow-x-auto rounded-lg border">
                        <table className="min-w-full border-collapse text-left text-sm">
                          <thead className="bg-muted/40">
                            <tr>
                              <th className="border-b px-3 py-2 font-medium">File Name</th>
                              <th className="border-b px-3 py-2 font-medium">Resolved To</th>
                              <th className="border-b px-3 py-2 font-medium">How</th>
                            </tr>
                          </thead>
                          <tbody>
                            {previewDiff.customer_resolutions.map((resolution) => (
                              <tr
                                key={`${resolution.file_name}-${resolution.resolved_to}`}
                                className="border-b last:border-b-0"
                              >
                                <td className="px-3 py-2">{resolution.file_name}</td>
                                <td className="px-3 py-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span>{resolution.resolved_to}</span>
                                    {resolution.is_new ? (
                                      <Badge
                                        variant="outline"
                                        className="border-emerald-200 text-emerald-700"
                                      >
                                        New
                                      </Badge>
                                    ) : null}
                                  </div>
                                </td>
                                <td className="px-3 py-2 text-muted-foreground">
                                  {mergeDetailByFileName.get(resolution.file_name) ??
                                    resolution.resolution_type}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  ) : null}
                </Card>
              </div>

              {previewDiff.skipped_rows > 0 ? (
                <Alert>
                  <AlertTitle>{previewDiff.skipped_rows} rows skipped</AlertTitle>
                  <AlertDescription className="space-y-3">
                    <p>
                      Review the warnings below before confirming the import.
                    </p>
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-3 rounded-lg border bg-muted/10 px-3 py-2 text-left text-sm"
                      onClick={() => toggleSection("warnings")}
                    >
                      <span>Skipped row details</span>
                      <ChevronDown
                        className={cn(
                          "size-4 transition-transform",
                          expandedSections.has("warnings") && "rotate-180",
                        )}
                      />
                    </button>
                    {expandedSections.has("warnings") ? (
                      <div className="space-y-2 rounded-lg border bg-muted/10 p-3">
                        {previewDiff.warnings.map((warning) => (
                          <p key={warning}>{warning}</p>
                        ))}
                      </div>
                    ) : null}
                  </AlertDescription>
                </Alert>
              ) : null}

              <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-xl border bg-muted/15 p-4 text-sm text-muted-foreground">
                <span>File: {preview.filename}</span>
                <span>Scope: {formatScopeLabel(scopeType)}</span>
                {savedTemplateName ? <span>Template: {savedTemplateName}</span> : null}
                <span>Total rows: {preview.total_rows}</span>
              </div>

              <Card className="bg-background/90">
                <CardHeader>
                  <CardTitle>Optional template</CardTitle>
                  <CardDescription>
                    Save the current mapping if you expect to import files with the
                    same structure again.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {savedTemplateName ? (
                    <div className="flex flex-wrap items-center gap-2 rounded-lg border bg-muted/20 p-3">
                      <Badge>{savedTemplateName}</Badge>
                      <p className="text-sm text-muted-foreground">
                        This template name will be shown for the current import.
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No template saved for this import yet.
                    </p>
                  )}

                  {showTemplateForm ? (
                    <form className="space-y-4" onSubmit={handleSaveTemplate}>
                      <div className="space-y-2">
                        <Label htmlFor="template-name">Template name</Label>
                        <Input
                          id="template-name"
                          value={templateName}
                          onChange={(event) => setTemplateName(event.target.value)}
                          placeholder="Pohoda monthly AR"
                          disabled={isSavingTemplate}
                        />
                      </div>
                      <div className="flex flex-col gap-3 sm:flex-row">
                        <Button
                          type="submit"
                          variant="outline"
                          disabled={!isMappingValid || isSavingTemplate}
                        >
                          {isSavingTemplate ? (
                            <>
                              <Loader2 className="size-4 animate-spin" />
                              Saving template...
                            </>
                          ) : (
                            "Save Template"
                          )}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          disabled={isSavingTemplate}
                          onClick={() => setShowTemplateForm(false)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </form>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={!isMappingValid}
                      onClick={() => setShowTemplateForm(true)}
                    >
                      Save Template
                    </Button>
                  )}
                </CardContent>
              </Card>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setPreviewDiff(null);
                      setPreviewError(null);
                      setExpandedSections(new Set());
                      setStep(candidates.length > 0 ? 3 : 2);
                    }}
                  >
                    Back
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="text-muted-foreground"
                    onClick={() => router.push("/dashboard")}
                  >
                    Cancel
                  </Button>
                </div>
                <Button
                  type="button"
                  size="lg"
                  disabled={!previewDiff || isLoadingPreview || isConfirming}
                  onClick={handleConfirmImport}
                >
                  {isConfirming ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Confirming...
                    </>
                  ) : (
                    "Confirm Import"
                  )}
                </Button>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
