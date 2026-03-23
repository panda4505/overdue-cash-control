"use client";

import type {
  ChangeEvent,
  DragEvent,
  FormEvent,
} from "react";
import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  ArrowRight,
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
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/contexts/auth-context";
import { apiFetch } from "@/lib/api";
import {
  SCOPE_OPTIONS,
  TARGET_FIELDS,
  TOTAL_TARGET_FIELDS,
  buildInitialMappings,
  buildMappingDict,
  collectAvailableHeaders,
  getMappingValidationErrors,
  type MappingSelection,
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
  const mappedFieldCount = Object.keys(mappingDict).length;
  const userMergedCount = Object.keys(mergeDecisions).length;
  const keptAsNewCount = candidates.length - userMergedCount;

  const resetPreviewState = () => {
    setUploadResult(null);
    setMappings([]);
    setMergeDecisions({});
    setSavedTemplateName(null);
    setShowTemplateForm(false);
    setTemplateName("");
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
          { stepNumber: 4, label: "Review" },
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
          <Card className="bg-background/90">
            <CardHeader>
              <CardTitle>Review &amp; Confirm</CardTitle>
              <CardDescription>
                Final check before the pending import is confirmed.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Filename
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {preview.filename}
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  File size
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {formatBytes(preview.file_size_bytes)}
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Total rows
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {preview.total_rows}
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Scope type
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {formatScopeLabel(scopeType)}
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Mapping summary
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {mappedFieldCount} of {TOTAL_TARGET_FIELDS} fields mapped
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Template
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {savedTemplateName ?? "No template saved"}
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Auto-matched
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {autoMerges.length}
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  User-merged
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {userMergedCount}
                </p>
              </div>
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                  Kept as new
                </p>
                <p className="mt-2 text-sm font-medium text-foreground">
                  {keptAsNewCount}
                </p>
              </div>
            </CardContent>
          </Card>

          {uploadResult?.duplicate_warning ? (
            <Alert>
              <AlertTitle>Duplicate warning</AlertTitle>
              <AlertDescription>{uploadResult.duplicate_warning}</AlertDescription>
            </Alert>
          ) : null}

          {!isMappingValid ? (
            <Alert variant="destructive">
              <AlertTitle>Mapping validation still needs attention</AlertTitle>
              <AlertDescription className="space-y-2">
                {mappingValidationErrors.map((message) => (
                  <p key={message}>{message}</p>
                ))}
              </AlertDescription>
            </Alert>
          ) : null}

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
            <CardFooter className="flex flex-col gap-3 sm:flex-row sm:justify-between">
              <Button
                type="button"
                variant="outline"
                onClick={() => setStep(candidates.length > 0 ? 3 : 2)}
              >
                Back
              </Button>
              <Button
                type="button"
                size="lg"
                disabled={!isMappingValid || isConfirming}
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
            </CardFooter>
          </Card>

          <Separator />

          <div className="rounded-xl border bg-muted/15 p-4 text-sm text-muted-foreground">
            Encoding: {preview.encoding ?? "Unknown"} • Delimiter:{" "}
            {preview.delimiter ?? "Unknown"} • Decimal separator:{" "}
            {preview.decimal_separator ?? "Unknown"} • Thousands separator:{" "}
            {preview.thousands_separator ?? "Unknown"} • Date format:{" "}
            {preview.date_format ?? "Not detected"}
          </div>
        </div>
      ) : null}
    </div>
  );
}
