import { z } from 'zod';

export const situacionOptions = [
  { value: 'en_desarrollo', label: 'En desarrollo' },
  { value: 'con_demo', label: 'Con demo' },
  { value: 'lance_1', label: 'Ya lancé 1 juego' },
  { value: 'lance_varios', label: 'Ya lancé varios' },
] as const;

export const equipoOptions = [
  { value: '1', label: '1' },
  { value: '2_a_5', label: '2 a 5' },
  { value: '6_a_20', label: '6 a 20' },
  { value: 'mas_20', label: 'Más de 20' },
] as const;

export const decisionPrecioOptions = [
  { value: 'a_ojo', label: 'A ojo' },
  { value: 'comparo', label: 'Comparo con juegos parecidos' },
  { value: 'publisher', label: 'Sigo lo que dice mi publisher' },
  { value: 'pregunto', label: 'Pregunto a otros devs' },
  { value: 'otro', label: 'Otro' },
] as const;

export const decisionFechaOptions = [
  { value: 'a_ojo', label: 'A ojo' },
  { value: 'comparo', label: 'Comparo con juegos parecidos' },
  { value: 'eventos', label: 'Pienso en eventos como Steam Next Fest' },
  { value: 'publisher', label: 'Me lo marca mi publisher' },
  { value: 'otro', label: 'Otro' },
] as const;

export const tiempoOptions = [
  { value: 'menos_1h', label: 'Menos de 1 hora' },
  { value: '1_a_5h', label: '1 a 5 horas' },
  { value: 'mas_5h', label: 'Más de 5 horas' },
  { value: 'no_investigo', label: 'No investigo' },
] as const;

export const pagariasOptions = [
  { value: 'no', label: 'No' },
  { value: 'solo_gratis', label: 'Solo si es gratis' },
  { value: 'hasta_5', label: 'Hasta 5 USD al mes' },
  { value: '5_a_15', label: '5 a 15 USD al mes' },
  { value: 'mas_15', label: 'Más de 15 USD al mes' },
  { value: 'reporte_unico', label: 'Pagaría por un reporte único' },
] as const;

const valuesOf = (opts: readonly { value: string }[]) =>
  opts.map((o) => o.value) as [string, ...string[]];

export const surveySchema = z
  .object({
    situacion: z.enum(valuesOf(situacionOptions), {
      errorMap: () => ({ message: 'Elige una opción' }),
    }),
    tamanoEquipo: z.enum(valuesOf(equipoOptions), {
      errorMap: () => ({ message: 'Elige una opción' }),
    }),
    pais: z.string().max(80).optional().default(''),
    decidePrecio: z
      .array(z.enum(valuesOf(decisionPrecioOptions)))
      .min(1, 'Elige al menos una opción'),
    decidePrecioOtro: z.string().max(200).optional().default(''),
    decideFecha: z
      .array(z.enum(valuesOf(decisionFechaOptions)))
      .min(1, 'Elige al menos una opción'),
    decideFechaOtro: z.string().max(200).optional().default(''),
    tiempoInvestigar: z.enum(valuesOf(tiempoOptions), {
      errorMap: () => ({ message: 'Elige una opción' }),
    }),
    infoTranquilidad: z.string().max(500).optional().default(''),
    usarias1a5: z
      .number({ invalid_type_error: 'Elige un valor del 1 al 5' })
      .int()
      .min(1, 'Elige un valor del 1 al 5')
      .max(5),
    pagarias: z.enum(valuesOf(pagariasOptions), {
      errorMap: () => ({ message: 'Elige una opción' }),
    }),
    contacto: z.string().max(120).optional().default(''),
  })
  .superRefine((val, ctx) => {
    if (val.decidePrecio.includes('otro') && !val.decidePrecioOtro?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['decidePrecioOtro'],
        message: 'Cuéntanos brevemente cuál',
      });
    }
    if (val.decideFecha.includes('otro') && !val.decideFechaOtro?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['decideFechaOtro'],
        message: 'Cuéntanos brevemente cuál',
      });
    }
  });

export type SurveyFormData = z.infer<typeof surveySchema>;
