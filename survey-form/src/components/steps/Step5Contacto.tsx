'use client';

import type { SurveyFormData } from '@/lib/schema';
import { TextField } from '../ui/TextField';

type Props = {
  data: Partial<SurveyFormData>;
  update: (patch: Partial<SurveyFormData>) => void;
  errors: Partial<Record<keyof SurveyFormData, string>>;
};

export function Step5Contacto({ data, update, errors }: Props) {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <TextField
          label="¿Quieres probar el prototipo?"
          optional
          value={data.contacto}
          onChange={(v) => update({ contacto: v })}
          placeholder="Tu correo o tu Instagram"
          error={errors.contacto}
        />
        <p className="mt-2 text-xs text-muted">
          Solo lo usamos para invitarte a probar PixelRadar. Es opcional.
        </p>
      </div>
    </div>
  );
}
