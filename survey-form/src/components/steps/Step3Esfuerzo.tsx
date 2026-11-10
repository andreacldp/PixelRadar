'use client';

import { tiempoOptions, type SurveyFormData } from '@/lib/schema';
import { OptionPill } from '../ui/OptionPill';
import { TextAreaField } from '../ui/TextAreaField';

type Props = {
  data: Partial<SurveyFormData>;
  update: (patch: Partial<SurveyFormData>) => void;
  errors: Partial<Record<keyof SurveyFormData, string>>;
};

export function Step3Esfuerzo({ data, update, errors }: Props) {
  return (
    <div className="flex flex-col gap-8">
      <fieldset>
        <legend className="mb-3 font-display text-base font-medium text-fg">
          ¿Cuánto te tomaría investigar eso a mano?
        </legend>
        <div className="flex flex-wrap gap-2" role="radiogroup">
          {tiempoOptions.map((opt) => (
            <OptionPill
              key={opt.value}
              name="tiempoInvestigar"
              label={opt.label}
              selected={data.tiempoInvestigar === opt.value}
              onClick={() => update({ tiempoInvestigar: opt.value })}
            />
          ))}
        </div>
        {errors.tiempoInvestigar && (
          <p className="mt-2 text-sm text-pink">{errors.tiempoInvestigar}</p>
        )}
      </fieldset>

      <TextAreaField
        label="¿Qué información te daría más tranquilidad al decidir?"
        optional
        value={data.infoTranquilidad}
        onChange={(v) => update({ infoTranquilidad: v })}
        placeholder="Por ejemplo: precios de juegos parecidos, mejores meses para lanzar…"
      />
    </div>
  );
}
