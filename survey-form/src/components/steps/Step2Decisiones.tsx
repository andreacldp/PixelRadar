'use client';

import { decisionPrecioOptions, decisionFechaOptions, type SurveyFormData } from '@/lib/schema';
import { OptionPill } from '../ui/OptionPill';
import { TextField } from '../ui/TextField';

type Props = {
  data: Partial<SurveyFormData>;
  update: (patch: Partial<SurveyFormData>) => void;
  errors: Partial<Record<keyof SurveyFormData, string>>;
};

function toggle(list: string[] | undefined, value: string): string[] {
  const current = list ?? [];
  return current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
}

export function Step2Decisiones({ data, update, errors }: Props) {
  return (
    <div className="flex flex-col gap-8">
      <fieldset>
        <legend className="mb-3 font-display text-base font-medium text-fg">
          ¿Cómo decides o decidiste el precio de tu juego?
        </legend>
        <div className="flex flex-wrap gap-2">
          {decisionPrecioOptions.map((opt) => (
            <OptionPill
              key={opt.value}
              type="checkbox"
              name="decidePrecio"
              label={opt.label}
              selected={(data.decidePrecio ?? []).includes(opt.value)}
              onClick={() => update({ decidePrecio: toggle(data.decidePrecio, opt.value) })}
            />
          ))}
        </div>
        {(data.decidePrecio ?? []).includes('otro') && (
          <div className="mt-3">
            <TextField
              label="¿Cuál?"
              value={data.decidePrecioOtro}
              onChange={(v) => update({ decidePrecioOtro: v })}
              error={errors.decidePrecioOtro}
            />
          </div>
        )}
        {errors.decidePrecio && <p className="mt-2 text-sm text-pink">{errors.decidePrecio}</p>}
      </fieldset>

      <fieldset>
        <legend className="mb-3 font-display text-base font-medium text-fg">
          ¿Y cómo decides la fecha de lanzamiento?
        </legend>
        <div className="flex flex-wrap gap-2">
          {decisionFechaOptions.map((opt) => (
            <OptionPill
              key={opt.value}
              type="checkbox"
              name="decideFecha"
              label={opt.label}
              selected={(data.decideFecha ?? []).includes(opt.value)}
              onClick={() => update({ decideFecha: toggle(data.decideFecha, opt.value) })}
            />
          ))}
        </div>
        {(data.decideFecha ?? []).includes('otro') && (
          <div className="mt-3">
            <TextField
              label="¿Cuál?"
              value={data.decideFechaOtro}
              onChange={(v) => update({ decideFechaOtro: v })}
              error={errors.decideFechaOtro}
            />
          </div>
        )}
        {errors.decideFecha && <p className="mt-2 text-sm text-pink">{errors.decideFecha}</p>}
      </fieldset>
    </div>
  );
}
