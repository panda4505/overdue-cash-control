"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function DashboardPage() {
  const { account } = useAuth();

  if (!account) {
    return <p className="text-sm text-muted-foreground">Loading account...</p>;
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <section className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-muted-foreground">
          Dashboard
        </p>
        <h1 className="text-3xl font-semibold tracking-tight">
          {account.company_name ?? "Your account"}
        </h1>
        <p className="text-muted-foreground">
          This milestone focuses on getting data in cleanly before the full
          dashboard lands.
        </p>
      </section>

      {account.first_import_at === null ? (
        <Card className="border-dashed border-border/80 bg-background/90">
          <CardHeader>
            <CardTitle>No imports yet</CardTitle>
            <CardDescription>
              Upload your first receivables file to start building the
              collections workspace.
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
      ) : (
        <Card className="bg-background/90">
          <CardHeader>
            <CardTitle>Dashboard coming soon</CardTitle>
            <CardDescription>
              Your import pipeline is ready. Richer analytics arrive in a later
              slice.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Last import processed on {formatDateTime(account.last_import_at ?? account.first_import_at)}.
            </p>
            <Link
              href="/imports/new"
              className={cn(
                buttonVariants({ variant: "outline", size: "lg" }),
                "justify-center",
              )}
            >
              Import another file
            </Link>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
