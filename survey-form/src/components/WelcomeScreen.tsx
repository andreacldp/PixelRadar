import { Logo } from './Logo';
import { FishDots } from './FishDots';

export function WelcomeScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="relative mx-auto flex min-h-dvh w-full max-w-xl flex-col items-center justify-center overflow-hidden px-6 py-12 text-center">
      <FishDots className="pointer-events-none absolute inset-x-0 top-10 mx-auto opacity-[0.08]" />
      <Logo className="mb-10" />
      <h1 className="font-display text-3xl font-semibold leading-tight text-fg sm:text-4xl">
        Hay miles de juegos en el mar.{' '}
        <span className="text-pink">Ayúdanos a leerlo.</span>
      </h1>
      <p className="mt-5 max-w-sm text-balance text-sm leading-relaxed text-muted sm:text-base">
        Somos estudiantes del Tec de Monterrey y queremos entender cómo los estudios indie deciden
        precio y fecha de lanzamiento. Son 3 minutos, es anónimo y no pedimos cifras de ventas ni
        datos privados.
      </p>
      <button
        type="button"
        onClick={onStart}
        className="mt-10 rounded-full bg-pink px-8 py-3 text-sm font-semibold text-black transition-transform duration-200 active:scale-95"
      >
        Empezar
      </button>
    </div>
  );
}
