import { Logo } from './Logo';
import { FishDots } from './FishDots';

export function ThankYouScreen() {
  return (
    <div className="relative mx-auto flex min-h-dvh w-full max-w-xl flex-col items-center justify-center overflow-hidden px-6 py-12 text-center">
      <FishDots className="pointer-events-none absolute inset-x-0 bottom-10 mx-auto opacity-[0.08]" />
      <Logo className="mb-10" />
      <h1 className="font-display text-3xl font-semibold leading-tight text-fg sm:text-4xl">
        Gracias por <span className="text-teal">nadar con nosotros.</span>
      </h1>
      <p className="mt-5 max-w-sm text-balance text-sm leading-relaxed text-muted sm:text-base">
        Tus respuestas ya quedaron en la corriente. Nos van a ayudar a construir una mejor
        herramienta para estudios indie como el tuyo.
      </p>
    </div>
  );
}
