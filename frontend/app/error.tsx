'use client';

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string };
    reset: () => void;
}) {
    return (
        <div className="flex h-screen items-center justify-center bg-white">
            <div className="text-center">
                <h2 className="text-xl font-bold text-gray-900 mb-2">Something went wrong</h2>
                <p className="text-sm text-gray-500 mb-4">{error.message || 'An unexpected error occurred.'}</p>
                <button
                    onClick={reset}
                    className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                >
                    Try again
                </button>
            </div>
        </div>
    );
}
