import { ReactNode } from "react";
import { Skeleton } from "./Skeleton";

interface Metric {
  label: string;
  value: ReactNode;
  description?: ReactNode;
  tone?: "neutral" | "income" | "expense";
}

interface Props {
  heading: string;
  context?: ReactNode;
  primary: Metric;
  supporting: Metric[];
  loading?: boolean;
  compact?: boolean;
  children?: ReactNode;
}

/** One reading order for financial summaries: result, supporting amounts, context. */
export function FinancialSummary({ heading, context, primary, supporting, loading, compact, children }: Props) {
  return <section className={`tf-summary${compact ? " tf-summary--compact" : ""}`} aria-label={heading} aria-busy={loading}>
    <header className="tf-summary-heading"><h2 className="ai7-type-section">{heading}</h2>{context && <p>{context}</p>}</header>
    <div className="tf-summary-content">
      <dl className="tf-summary-primary"><dt>{primary.label}</dt><dd data-tone={primary.tone ?? "neutral"}>{loading ? <Skeleton className="h-10 w-40 max-w-full" /> : primary.value}</dd>{primary.description && <dd className="tf-summary-description">{primary.description}</dd>}</dl>
      <dl className="tf-summary-support">{supporting.map((item) => <div key={item.label}><dt>{item.label}</dt><dd data-tone={item.tone ?? "neutral"}>{loading ? <Skeleton className="h-6 w-28 max-w-full" /> : item.value}</dd>{item.description && <dd className="tf-summary-description">{item.description}</dd>}</div>)}</dl>
    </div>
    {children && <div className="tf-summary-note">{children}</div>}
  </section>;
}
