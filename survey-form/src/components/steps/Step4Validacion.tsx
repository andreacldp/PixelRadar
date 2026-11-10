'use client';

import { pagariasOptions, type SurveyFormData } from '@/lib/schema';
import { OptionPill } from '../ui/OptionPill';
import { ScaleField } from '../ui/ScaleField';

type Props = {
  data: Partial<SurveyFormData>;
  update: (patch: Partial<SurveyFormData>) => void;
  errors: Partial<Record<keyof SurveyFormData, string>>;
};

export function Step4Validacion({ data, update, errors }: Props) {
  return (
    <div className="flex flex-col gap-8">
      <fieldset>
        <legend className="mb-3 font-display text-base font-medium text-fg">
          Si una herramienta te mostrara juegos parecidos al tuyo en Steam, un rango de precio y
          los meses de lanzamiento más comunes, ¿la usarías?
        </legend>
        <ScaleField
          value={data.usarias1a5}
          onChange={(v) => update({ usarias1a5: v })}
          minLabel="No la usaría"
          maxLabel="La usaría seguro"
        />
        {errors.usarias1a5 && <p className="mt-2 text-sm text-pink">{errors.usarias1a5}</p>}
      </fieldset>

      <fieldset>
        <legend className="mb-3 font-display text-base font-medium text-fg">
          ¿Pagarías por algo así?
        </legend>
        <div className="flex flex-wrap gap-2" role="radiogroup">
          {pagariasOptions.map((opt) => (
            <OptionPill
              key={opt.value}
              name="pagarias"
              label={opt.label}
              selected={data.pagarias === opt.value}
              onClick={() => update({ pagarias: opt.value })}
            />
          ))}
        </div>
        {errors.pagarias && <p className="mt-2 text-sm text-pink">{errors.pagarias}</p>}
      </fieldset>
    </div>
  );
}
