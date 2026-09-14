export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-yellow text-sm font-bold">CL</span>
      <span className="text-[17px] font-semibold tracking-tight">CreditLens</span>
    </div>
  );
}

export function PageTitle({
  kicker,
  title,
  text,
}: {
  kicker?: string;
  title: string;
  text?: string;
}) {
  return (
    <header className="mb-6 max-w-3xl">
      {kicker && <p className="mb-2 text-sm font-medium text-muted">{kicker}</p>}
      <h1 className="text-[32px] font-semibold leading-tight tracking-tight md:text-[40px]">{title}</h1>
      {text && <p className="mt-3 text-[16px] leading-6 text-muted">{text}</p>}
    </header>
  );
}

export function TechPill({ children }: { children: string }) {
  return <span className="pill">{children}</span>;
}
