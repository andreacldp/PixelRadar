'use client';

import { situacionOptions, equipoOptions, type SurveyFormData } from '@/lib/schema';
import { OptionPill } from '../ui/OptionPill';
import { TextField } from '../ui/TextField';

type Props = {
  data: Partial<SurveyFormData>;
  update: (patch: Partial<SurveyFormData>) => void;
  errors: Partial<Record<keyof SurveyFormData, string>>;
};

export function Step1Perfil({ data, update, errors }: Props) {
  return (
    <div className="flex flex-col gap-8">
      <fieldset>
        <legend className="mb-3 font-display text-base font-medium text-fg">
          ¿Cuál es tu situación?
        </legend>
        <div className="flex flex-wrap gap-2" role="radiogroup">
          {situacionOptions.map((opt) => (
            <OptionPill
              key={opt.value}
              name="situacion"
              label={opt.label}
              selected={data.situacion === opt.value}
              onClick={() => update({ situacion: opt.value })}
            />
          ))}
        </div>
        {errors.situacion && <p className="mt-2 text-sm text-pink">{errors.situacion}</p>}
      </fieldset>

      <fieldset>
        <legend className="mb-3 font-display text-base font-medium text-fg">
          ¿Cuántas personas son en tu equipo?
        </legend>
        <div className="flex flex-wrap gap-2" role="radiogroup">
          {equipoOptions.map((opt) => (
            <OptionPill
              key={opt.value}
              name="tamanoEquipo"
              label={opt.label}
              selected={data.tamanoEquipo === opt.value}
              onClick={() => update({ tamanoEquipo: opt.value })}
            />
          ))}
        </div>
        {errors.tamanoEquipo && <p className="mt-2 text-sm text-pink">{errors.tamanoEquipo}</p>}
      </fieldset>

      <TextField
        label="¿En qué país estás?"
        optional
        value={data.pais}
        onChange={(v) => update({ pais: v })}
        placeholder="México, Argentina, Colombia…"
      />
    </div>
  );
}
