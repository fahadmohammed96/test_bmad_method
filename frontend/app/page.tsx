import { appCopy } from "@/lib/copy/app";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-start justify-center gap-6 px-6">
      <p className="text-muted text-sm tracking-wide uppercase">
        {appCopy.scaffoldEtichetta}
      </p>
      <h1 className="font-display text-4xl font-semibold">{appCopy.nome}</h1>
      <p className="text-lg leading-relaxed">{appCopy.scaffoldNota}</p>
    </main>
  );
}
