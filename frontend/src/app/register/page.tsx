"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

export default function RegisterPage() {
  const { user, account, isLoading, register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isLoading && user) {
      router.replace(account?.company_name ? "/dashboard" : "/onboarding");
    }
  }, [account, isLoading, router, user]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setError(null);
    setIsSubmitting(true);

    try {
      await register(email, password);
      router.replace("/onboarding");
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "Unable to create your account.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading || user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted/20">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,_#f8fafc_0%,_#f5f3ff_100%)] px-6 py-12">
      <Card className="w-full max-w-md border-border/80 bg-background/95 shadow-lg">
        <CardHeader className="space-y-2">
          <CardTitle className="text-2xl">Create your account</CardTitle>
          <CardDescription>
            Register with an email and password to start onboarding.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="register-email">Email</Label>
              <Input
                id="register-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="user@example.com"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="register-password">Password</Label>
              <Input
                id="register-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="At least 8 characters"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm password</Label>
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Repeat your password"
                required
              />
            </div>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Registration failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Creating account..." : "Create account"}
            </Button>
          </form>

          <p className="text-sm text-muted-foreground">
            Already registered?{" "}
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "link" }), "h-auto px-0")}
            >
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
