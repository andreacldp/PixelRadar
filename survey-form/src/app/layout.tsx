import type { Metadata } from 'next';
import { Space_Grotesk, Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['500', '600', '700'],
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600'],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500'],
});

const SITE_DESCRIPTION =
  'Somos estudiantes del Tec de Monterrey y queremos entender cómo los estudios indie deciden precio y fecha de lanzamiento. 3 minutos, anónimo.';

export const metadata: Metadata = {
  // TODO: reemplazar por el dominio real una vez desplegado en Vercel.
  metadataBase: new URL('https://pixelradar-survey.vercel.app'),
  title: 'PixelRadar — Encuesta para estudios indie',
  description: SITE_DESCRIPTION,
  openGraph: {
    title: 'PixelRadar — Encuesta para estudios indie',
    description: SITE_DESCRIPTION,
    images: ['/og-image.png'],
    type: 'website',
    locale: 'es_MX',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'PixelRadar — Encuesta para estudios indie',
    description: SITE_DESCRIPTION,
    images: ['/og-image.png'],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body
        className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} font-body bg-bg text-fg antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
