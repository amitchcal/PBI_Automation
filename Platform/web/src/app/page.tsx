"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Image from "next/image";
import { Button, Field, inputCls, Notice } from "@/components/ui";

export default function SignIn() {
  const router = useRouter();
  const [name, setName] = useState("Amit Chakraborty");
  const [err, setErr] = useState("");
  function go(e: React.FormEvent) {
    e.preventDefault();
    if (name.trim().length < 3) { setErr("Please type your full name."); return; }
    localStorage.setItem("actor", name.trim());
    router.push("/engagements");
  }
  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden lg:flex bg-secondary text-on-secondary p-14 flex-col justify-between">
        <Image src="/brand/logo-full-light.png" alt="Meridian Analytics" width={260} height={67} priority />
        <div>
          <h1 className="text-4xl font-semibold leading-tight max-w-lg">From your data to a dashboard you can trust.</h1>
          <p className="mt-5 text-slate-300 max-w-md leading-relaxed">Twelve clear steps. You decide the meaning of every number; every number is checked against an independent calculation before you see it.</p>
        </div>
        <p className="text-sm text-slate-400">Prototype: signing in is a placeholder and stores your name only in this browser.</p>
      </div>
      <main className="flex items-center justify-center p-6 sm:p-12">
        <form onSubmit={go} className="w-full max-w-md" noValidate>
          <Image src="/brand/logo-full.png" alt="Meridian Analytics" width={200} height={52} className="lg:hidden mb-8" priority />
          <h2 className="text-2xl font-semibold mb-1">Welcome</h2>
          <p className="text-muted mb-6">Sign in to continue your engagement.</p>
          <Field label="Your name" htmlFor="name" error={err} help="Recorded next to every decision you make.">
            <input id="name" className={inputCls} value={name} onChange={(e) => { setName(e.target.value); setErr(""); }} autoComplete="name" aria-describedby="name-help" />
          </Field>
          <Button type="submit" className="w-full">Continue</Button>
          <div className="mt-6"><Notice>Sample data only. No password is needed in this prototype; real sign-in and roles come with the deployment steps.</Notice></div>
        </form>
      </main>
    </div>
  );
}
