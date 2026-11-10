'use client';

import { useState } from 'react';
import { surveySchema, type SurveyFormData } from '@/lib/schema';
import { ProgressBar } from './ProgressBar';
import { WelcomeScreen } from './WelcomeScreen';
import { ThankYouScreen } from './ThankYouScreen';
import { Step1Perfil } from './steps/Step1Perfil';
import { Step2Decisiones } from './steps/Step2Decisiones';
import { Step3Esfuerzo } from './steps/Step3Esfuerzo';
import { Step4Validacion } from './steps/Step4Validacion';
import { Step5Contacto } from './steps/Step5Contacto';

const TOTAL_STEPS = 5;

const STEP_FIELDS: Record<number, (keyof SurveyFormData)[]> = {
  1: ['situacion', 'tamanoEquipo'],
  2: ['decidePrecio', 'decidePrecioOtro', 'decideFecha', 'decideFechaOtro'],
  3: ['tiempoInvestigar'],
  4: ['usarias1a5', 'pagarias'],
  5: [],
};

const STEPS = [Step1Perfil, Step2Decisiones, Step3Esfuerzo, Step4Validacion, Step5Contacto];

const initialData: Partial<SurveyFormData> = {
  pais: '',
  decidePrecio: [],
  decidePrecioOtro: '',
  decideFecha: [],
  decideFechaOtro: '',
  infoTranquilidad: '',
  contacto: '',
};

type Phase = 'welcome' | 'form' | 'thanks';

export function SurveyForm() {
  const [phase, setPhase] = useState<Phase>('welcome');
  const [step, setStep] = useState(1);
  const [data, setData] = useState<Partial<SurveyFormData>>(initialData);
  const [honeypot, setHoneypot] = useState('');
  const [errors, setErrors] = useState<Partial<Record<keyof SurveyFormData, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function update(patch: Partial<SurveyFormData>) {
    setData((d) => ({ ...d, ...patch }));
  }

  function validateStep(): boolean {
    const result = surveySchema.safeParse(data);
    const relevant = STEP_FIELDS[step];
    const nextErrors: Partial<Record<keyof SurveyFormData, string>> = {};

    if (!result.success) {
      for (const issue of result.error.issues) {
        const key = issue.path[0] as keyof SurveyFormData;
        if (relevant.includes(key)) {
          nextErrors[key] = issue.message;
        }
      }
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  function handleNext() {
    if (!validateStep()) return;
    if (step === TOTAL_STEPS) {
      void handleSubmit();
    } else {
      setStep((s) => s + 1);
    }
  }

  function handleBack() {
    setErrors({});
    setStep((s) => Math.max(1, s - 1));
  }

  async function handleSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...data, company_website: honeypot }),
      });
      if (!res.ok) throw new Error('request_failed');
      setPhase('thanks');
    } catch {
      setSubmitError('No pudimos enviar tus respuestas. Intenta de nuevo en un momento.');
    } finally {
      setSubmitting(false);
    }
  }

  if (phase === 'welcome') {
    return <WelcomeScreen onStart={() => setPhase('form')} />;
  }

  if (phase === 'thanks') {
    return <ThankYouScreen />;
  }

  const StepComponent = STEPS[step - 1];

  return (
    <div className="relative mx-auto flex min-h-dvh w-full max-w-xl flex-col px-5 py-6">
      <ProgressBar step={step} total={TOTAL_STEPS} />
      <p className="mt-3 font-mono text-xs uppercase tracking-widest text-muted">
        Paso {step} de {TOTAL_STEPS}
      </p>

      <div key={step} className="mt-8 flex-1 animate-fadeSlideIn">
        <StepComponent data={data} update={update} errors={errors} />
      </div>

      {/* Honeypot: invisible para personas, visible para bots que rellenan todo */}
      <input
        type="text"
        value={honeypot}
        onChange={(e) => setHoneypot(e.target.value)}
        name="company_website"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="absolute left-[-9999px] top-auto h-px w-px overflow-hidden"
      />

      {submitError && <p className="mt-4 text-sm text-pink">{submitError}</p>}

      <div className="mt-8 flex items-center justify-between gap-4">
        <button
          type="button"
          onClick={handleBack}
          disabled={step === 1 || submitting}
          className="rounded-full px-4 py-2 text-sm font-medium text-muted transition-colors hover:text-fg disabled:opacity-0"
        >
          Atrás
        </button>
        <button
          type="button"
          onClick={handleNext}
          disabled={submitting}
          className="rounded-full bg-pink px-6 py-3 text-sm font-semibold text-black transition-transform duration-200 active:scale-95 disabled:opacity-60"
        >
          {submitting ? 'Enviando…' : step === TOTAL_STEPS ? 'Enviar' : 'Continuar'}
        </button>
      </div>
    </div>
  );
}
