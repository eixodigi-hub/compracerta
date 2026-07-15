import { createFileRoute, Link, useNavigate, useSearch } from "@tanstack/react-router";
import { useEffect, useState, type FormEvent } from "react";
import { z } from "zod";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { supabase } from "@/integrations/supabase/client";
import { Loader2 } from "lucide-react";

const searchSchema = z.object({
  redirect: z.string().optional(),
  mode: z.enum(["login", "signup", "recover"]).optional(),
});

export const Route = createFileRoute("/auth")({
  validateSearch: searchSchema,
  head: () => ({
    meta: [
      { title: "Entrar ou cadastrar — Compra Certa Marília" },
      { name: "description", content: "Acesse sua conta ou crie uma para salvar suas listas de compras." },
      { property: "og:title", content: "Entrar ou cadastrar — Compra Certa Marília" },
      { property: "og:description", content: "Acesse sua conta ou crie uma para salvar suas listas de compras." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AuthPage,
});

const loginSchema = z.object({
  email: z.string().trim().email("Informe um e-mail válido").max(255),
  password: z.string().min(6, "A senha deve ter pelo menos 6 caracteres").max(128),
});

const signupSchema = z.object({
  fullName: z.string().trim().min(2, "Informe seu nome").max(100),
  email: z.string().trim().email("Informe um e-mail válido").max(255),
  password: z.string().min(6, "A senha deve ter pelo menos 6 caracteres").max(128),
});

const recoverSchema = z.object({
  email: z.string().trim().email("Informe um e-mail válido").max(255),
});

function AuthPage() {
  const navigate = useNavigate();
  const search = useSearch({ from: "/auth" });
  const [tab, setTab] = useState<"login" | "signup" | "recover">(search.mode ?? "login");

  // If already signed in, bounce to redirect target (or home).
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        navigate({ to: search.redirect ?? "/", replace: true });
      }
    });
  }, [navigate, search.redirect]);

  return (
    <div className="mx-auto max-w-md px-4 py-8 md:py-14">
      <h1 className="text-center text-2xl font-bold">Bem-vindo</h1>
      <p className="mt-1 text-center text-sm text-muted-foreground">
        Entre na sua conta ou crie uma nova.
      </p>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)} className="mt-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="login">Entrar</TabsTrigger>
          <TabsTrigger value="signup">Cadastrar</TabsTrigger>
        </TabsList>

        <TabsContent value="login" className="mt-6">
          <LoginForm onRecover={() => setTab("recover")} redirect={search.redirect} />
        </TabsContent>

        <TabsContent value="signup" className="mt-6">
          <SignupForm redirect={search.redirect} />
        </TabsContent>

        {tab === "recover" && (
          <TabsContent value="recover" forceMount className="mt-6">
            <RecoverForm onBack={() => setTab("login")} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

function LoginForm({ onRecover, redirect }: { onRecover: () => void; redirect?: string }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const parsed = loginSchema.safeParse({
      email: form.get("email"),
      password: form.get("password"),
    });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Dados inválidos");
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword(parsed.data);
    setLoading(false);
    if (error) {
      toast.error(
        error.message === "Invalid login credentials"
          ? "E-mail ou senha incorretos"
          : error.message,
      );
      return;
    }
    toast.success("Bem-vindo de volta!");
    navigate({ to: redirect ?? "/", replace: true });
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="login-email">E-mail</Label>
        <Input id="login-email" name="email" type="email" autoComplete="email" required />
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="login-pass">Senha</Label>
          <button
            type="button"
            onClick={onRecover}
            className="text-xs font-medium text-primary hover:underline"
          >
            Esqueci minha senha
          </button>
        </div>
        <Input
          id="login-pass"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
      </div>
      <Button className="w-full" disabled={loading}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Entrar"}
      </Button>
    </form>
  );
}

function SignupForm({ redirect }: { redirect?: string }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const parsed = signupSchema.safeParse({
      fullName: form.get("fullName"),
      email: form.get("email"),
      password: form.get("password"),
    });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Dados inválidos");
      return;
    }
    setLoading(true);
    const { data, error } = await supabase.auth.signUp({
      email: parsed.data.email,
      password: parsed.data.password,
      options: {
        emailRedirectTo: `${window.location.origin}/`,
        data: { full_name: parsed.data.fullName, display_name: parsed.data.fullName },
      },
    });
    setLoading(false);

    if (error) {
      toast.error(
        error.message === "User already registered"
          ? "Este e-mail já está cadastrado. Faça login."
          : error.message,
      );
      return;
    }

    if (data.session) {
      toast.success("Conta criada com sucesso!");
      navigate({ to: redirect ?? "/", replace: true });
    } else {
      toast.success("Confira seu e-mail para confirmar a conta.");
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="signup-name">Nome</Label>
        <Input id="signup-name" name="fullName" autoComplete="name" required />
      </div>
      <div className="space-y-2">
        <Label htmlFor="signup-email">E-mail</Label>
        <Input id="signup-email" name="email" type="email" autoComplete="email" required />
      </div>
      <div className="space-y-2">
        <Label htmlFor="signup-pass">Senha</Label>
        <Input
          id="signup-pass"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={6}
        />
        <p className="text-xs text-muted-foreground">Mínimo de 6 caracteres.</p>
      </div>
      <Button className="w-full" disabled={loading}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Criar conta"}
      </Button>
    </form>
  );
}

function RecoverForm({ onBack }: { onBack: () => void }) {
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const parsed = recoverSchema.safeParse({ email: form.get("email") });
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "E-mail inválido");
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.resetPasswordForEmail(parsed.data.email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    setLoading(false);
    if (error) {
      toast.error(error.message);
      return;
    }
    setSent(true);
    toast.success("Enviamos um link para redefinir sua senha.");
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Recuperar senha</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Informe seu e-mail para receber o link de redefinição.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="recover-email">E-mail</Label>
          <Input id="recover-email" name="email" type="email" autoComplete="email" required />
        </div>
        <Button className="w-full" disabled={loading || sent}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : sent ? "E-mail enviado" : "Enviar link"}
        </Button>
      </form>
      <button
        type="button"
        onClick={onBack}
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        ← Voltar para o login
      </button>
      <p className="text-xs text-muted-foreground">
        Já tem conta?{" "}
        <Link to="/auth" search={{ mode: "login" }} className="text-primary hover:underline">
          Entrar
        </Link>
      </p>
    </div>
  );
}
