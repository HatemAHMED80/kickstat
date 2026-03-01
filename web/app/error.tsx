'use client';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen bg-[#09090b] text-white flex items-center justify-center">
      <div className="text-center">
        <h2 className="text-xl font-bold mb-2">Une erreur est survenue</h2>
        <p className="text-zinc-500 text-sm mb-4">{error.message}</p>
        <button
          onClick={reset}
          className="px-4 py-2 bg-violet-600 rounded-lg text-sm hover:bg-violet-500 transition"
        >
          Réessayer
        </button>
      </div>
    </div>
  );
}
