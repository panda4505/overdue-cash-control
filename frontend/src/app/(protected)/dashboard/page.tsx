"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  AlertTriangle,
  FileSpreadsheet,
  RefreshCw,
  Users,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/contexts/auth-context";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AgingBucket {
  label: string;
  min_days: number;
  max_days: number | null;
  count: number;
  amount: string;
  is_overdue: boolean;
}

interface TopExposure {
  customer_name: string;
  customer_id: string;
  total_overdue: string;
  overdue_invoice_count: number;
  oldest_overdue_days: number;
}

interface RecentChange {
  id: string;
  action_type: string;
  description: string;
  invoice_number: string | null;
  customer_name: string | null;
  created_at: string;
}

interface LastImport {
  id: string;
  confirmed_at: string;
  original_filename: string;
  invoices_created: number;
  invoices_updated: number;
  invoices_disappeared: number;
  invoices_unchanged: number;
  method: string;
}

interface DashboardData {
  total_overdue_amount: string;
  total_overdue_count: number;
  overdue_today_count: number;
  overdue_today_amount: string;
  disputed_count: number;
  possibly_paid_count: number;
  aging_buckets: AgingBucket[];
  top_exposure: TopExposure | null;
  recent_changes: RecentChange[];
  last_import: LastImport | null;
  is_data_stale: boolean;
  currency: string;
  first_import_at: string | null;
}

function formatAmount(amount: string, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(amount));
}

function relativeTime(isoString: string): string {
  const now = new Date();
  const then = new Date(isoString);
  const diffMs = now.getTime() - then.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays === 1) return "yesterday";
  return `${diffDays}d ago`;
}

function activityIcon(actionType: string) {
  switch (actionType) {
    case "import_committed":
      return <FileSpreadsheet className="size-4 text-sky-600" />;
    case "invoice_disappeared":
      return <AlertCircle className="size-4 text-amber-600" />;
    case "anomaly_flagged":
      return <AlertCircle className="size-4 text-destructive" />;
    case "customer_merged":
      return <Users className="size-4 text-foreground" />;
    case "invoice_updated":
      return <RefreshCw className="size-4 text-muted-foreground" />;
    default:
      return <AlertCircle className="size-4 text-muted-foreground" />;
  }
}

function agingRowClass(index: number) {
  switch (index) {
    case 0:
      return "text-muted-foreground";
    case 2:
      return "text-orange-700";
    case 3:
      return "text-amber-700";
    case 4:
      return "text-destructive";
    default:
      return "text-foreground";
  }
}

export default function DashboardPage() {
  const { account } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiFetch<DashboardData>("/dashboard");
      setData(response);
    } catch (loadError) {
      setError(
        loadError instanceof Error ? loadError.message : "Unable to load dashboard.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  if (!account) {
    return <p className="text-sm text-muted-foreground">Loading account...</p>;
  }

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Unable to load dashboard</AlertTitle>
          <AlertDescription className="space-y-4">
            <p>{error ?? "The dashboard data is unavailable right now."}</p>
            <Button type="button" variant="outline" onClick={() => void loadDashboard()}>
              Retry
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (data.first_import_at === null) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <Card className="border-dashed border-border/80 bg-background/90">
          <CardHeader className="space-y-2">
            <CardTitle>No imports yet</CardTitle>
            <CardDescription>
              Upload your first receivables file and we will turn it into a live
              overdue picture for your team.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/imports/new"
              className={cn(buttonVariants({ size: "lg" }), "justify-center")}
            >
              Start a new import
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6">
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">
            {account.company_name ?? "Your account"}
          </h1>
          {data.is_data_stale ? (
            <Badge
              variant="outline"
              className="border-amber-500/50 text-amber-700"
            >
              Stale data
            </Badge>
          ) : null}
        </div>
        <p className="text-muted-foreground">Overdue Cash Position</p>
      </section>

      {data.is_data_stale && data.last_import ? (
        <Alert className="border-amber-500/50 text-amber-700 [&>svg]:text-amber-600">
          <AlertTriangle className="size-4" />
          <AlertTitle>Data may be stale</AlertTitle>
          <AlertDescription>
            Last import was {relativeTime(data.last_import.confirmed_at)} ago.{" "}
            <Link
              href="/imports/new"
              className={cn(
                buttonVariants({ variant: "link" }),
                "h-auto px-0 text-amber-700 hover:text-amber-800",
              )}
            >
              Import a fresh file
            </Link>
            .
          </AlertDescription>
        </Alert>
      ) : null}

      {data.total_overdue_count > 0 ? (
        <Card className="border-rose-200 bg-[linear-gradient(135deg,_rgba(255,241,242,0.95)_0%,_rgba(255,247,237,0.98)_100%)] shadow-md">
          <CardContent className="space-y-3 p-6">
            <p className="text-2xl font-semibold tracking-tight text-foreground">
              You have{" "}
              {formatAmount(data.total_overdue_amount, data.currency)} overdue
              across {data.total_overdue_count} invoices.
            </p>
            {data.top_exposure ? (
              <p className="max-w-4xl text-sm leading-6 text-muted-foreground">
                Your biggest exposure is {data.top_exposure.customer_name} with{" "}
                {formatAmount(data.top_exposure.total_overdue, data.currency)} across{" "}
                {data.top_exposure.overdue_invoice_count} invoices, oldest{" "}
                {data.top_exposure.oldest_overdue_days} days overdue.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-l-4 border-l-destructive bg-background/90">
          <CardHeader className="space-y-2 pb-3">
            <CardDescription>Total Overdue</CardDescription>
            <CardTitle className="text-3xl">
              {formatAmount(data.total_overdue_amount, data.currency)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              {data.total_overdue_count} invoices
            </p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-500 bg-background/90">
          <CardHeader className="space-y-2 pb-3">
            <CardDescription>Overdue Today</CardDescription>
            <CardTitle className="text-3xl">{data.overdue_today_count}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-sm font-medium text-foreground">
              {formatAmount(data.overdue_today_amount, data.currency)}
            </p>
            <p className="text-sm text-muted-foreground">became overdue today</p>
          </CardContent>
        </Card>

        <Card className="bg-background/90">
          <CardHeader className="space-y-2 pb-3">
            <CardDescription>Disputes Open</CardDescription>
            <CardTitle className="text-3xl">{data.disputed_count}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">disputed invoices</p>
          </CardContent>
        </Card>

        <Card className="bg-background/90">
          <CardHeader className="space-y-2 pb-3">
            <CardDescription>Payment Review</CardDescription>
            <CardTitle className="text-3xl">{data.possibly_paid_count}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">possibly paid - verify</p>
          </CardContent>
        </Card>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <Card className="bg-background/90">
          <CardHeader>
            <CardTitle>Aging breakdown</CardTitle>
            <CardDescription>
              Current exposure split by how long invoices have been due.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Bucket</TableHead>
                  <TableHead className="text-right">Invoices</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.aging_buckets.map((bucket, index) => (
                  <TableRow key={bucket.label} className={agingRowClass(index)}>
                    <TableCell className="font-medium">{bucket.label}</TableCell>
                    <TableCell className="text-right">{bucket.count}</TableCell>
                    <TableCell className="text-right font-medium">
                      {formatAmount(bucket.amount, data.currency)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card className="bg-background/90">
          <CardHeader>
            <CardTitle>Recent changes</CardTitle>
            <CardDescription>
              The latest operator-relevant activity from imports and reconciliations.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.recent_changes.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No changes recorded yet.
              </p>
            ) : (
              <div className="space-y-4">
                {data.recent_changes.map((change) => (
                  <div
                    key={change.id}
                    className="flex items-start gap-3 rounded-lg border bg-muted/20 p-3"
                  >
                    <div className="mt-0.5 flex size-8 items-center justify-center rounded-full bg-background">
                      {activityIcon(change.action_type)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm leading-6 text-foreground">
                        {change.description}
                      </p>
                    </div>
                    <p className="shrink-0 text-xs text-muted-foreground">
                      {relativeTime(change.created_at)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <section>
        {data.last_import ? (
          <p className="text-sm text-muted-foreground">
            {data.last_import.original_filename} imported{" "}
            {relativeTime(data.last_import.confirmed_at)} -{" "}
            {data.last_import.invoices_created} created,{" "}
            {data.last_import.invoices_updated} updated,{" "}
            {data.last_import.invoices_disappeared} disappeared
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            No imports yet.{" "}
            <Link href="/imports/new" className="underline underline-offset-4">
              Start a new import
            </Link>
            .
          </p>
        )}
      </section>
    </div>
  );
}
