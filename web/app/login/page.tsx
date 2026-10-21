// G01 Login: the form is a client component (it holds the credentials and
// the session token), and the page is a server component so the form is in
// the first paint rather than arriving after hydration. The ?next= target
// is read here, on the server, which is also what makes that possible.
import LoginForm from "./login-form";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const params = await searchParams;
  const raw = params.next;
  const next = Array.isArray(raw) ? (raw[0] ?? "/agent") : (raw ?? "/agent");
  return (
    <main data-screen="G01" className="flex min-h-[60vh] items-center justify-center">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span
            aria-hidden="true"
            className="flex h-12 w-12 items-center justify-center rounded-xl text-lg font-bold text-white"
            style={{
              background: "linear-gradient(135deg, var(--color-accent), var(--color-accent-2))",
              boxShadow: "0 4px 16px rgb(79 70 229 / 0.4)",
            }}
          >
            P
          </span>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
            <p className="mt-1 text-sm text-text-2">
              Autonomous procurement missions with approval gates.
            </p>
          </div>
        </div>
        <LoginForm next={next} />
      </div>
    </main>
  );
}
