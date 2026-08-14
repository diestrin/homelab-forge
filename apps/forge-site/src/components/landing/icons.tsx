type IconProps = {
  className?: string;
};

export function IconDeclarativeHost({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect x="6" y="10" width="36" height="28" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M14 18h20M14 24h14M14 30h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="36" cy="30" r="4" stroke="currentColor" strokeWidth="1.5" />
      <path d="M24 6v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconSandbox({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect x="8" y="14" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <rect x="26" y="14" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <rect x="17" y="28" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M15 14V10a2 2 0 012-2h14a2 2 0 012 2v4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function IconKubernetes({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M24 8l14 8v16l-14 8-14-8V16l14-8z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="24" cy="24" r="5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M24 19v-3M29 24h3M24 29v3M19 24h-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconSecretsGitops({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect x="14" y="20" width="20" height="18" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M20 20v-4a4 4 0 018 0v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="24" cy="29" r="2" fill="currentColor" />
      <path d="M8 14h6M34 14h6M8 34h6M34 34h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconFactory({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path d="M10 38V18l8-6 8 6v20" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M26 38V22l8-6 8 6v16" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M16 38v-8h6v8M34 38v-8h4v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="24" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function IconHostWatch({ className }: IconProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <circle cx="24" cy="24" r="14" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="24" cy="24" r="6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M24 10v4M24 34v4M10 24h4M34 24h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M30 18l2-2M16 30l-2 2M30 30l2 2M16 18l-2-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconIntake({ className }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <path d="M6 10h20M6 16h14M6 22h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="24" cy="22" r="4" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function IconPlanGate({ className }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <rect x="8" y="6" width="16" height="20" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M12 12h8M12 16h8M12 20h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M22 24l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconWorker({ className }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <rect x="6" y="8" width="20" height="16" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 14h12M10 18h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M16 24v4M12 28h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconReview({ className }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <circle cx="16" cy="12" r="5" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 26c0-4 3.5-7 8-7s8 3 8 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M22 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconDeploy({ className }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <path d="M16 6v14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M11 15l5 5 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M6 22v4h20v-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function IconChevron({ className, open }: IconProps & { open?: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      className={`${className ?? ""} transition-transform duration-200 ${open ? "rotate-180" : ""}`}
      aria-hidden="true"
    >
      <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
