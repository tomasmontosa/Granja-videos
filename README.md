# YouTube Short piloto — arquitectura gratuita

Este proyecto genera un Short vertical a partir de un guion original, narración TTS y un video de stock de Pexels, y lo sube a YouTube como **privado** usando la API oficial.

## Qué hace y qué no hace
- Sí: descarga material de stock desde Pexels, genera voz con `edge-tts`, compone un MP4 9:16 con FFmpeg, agrega subtítulos y sube el resultado.
- No: no investiga tendencias por sí solo ni escribe nuevos guiones con un modelo generativo; el guion del piloto está en `scripts/sol_desaparece.json`.
- No: no publica públicamente. Los proyectos de YouTube API no verificados pueden quedar restringidos a privado hasta completar la auditoría de YouTube. Ver documentación oficial.
- No garantizamos monetización; YouTube excluye contenido repetitivo o producido en masa sin valor original.

## Necesitás
1. Cuenta de GitHub.
2. Clave de API de Pexels (gratuita): https://www.pexels.com/api/
3. Proyecto en Google Cloud con YouTube Data API v3 habilitada.
4. OAuth 2.0 Client ID/secret y refresh token con el scope `https://www.googleapis.com/auth/youtube.upload`.
5. Un canal de YouTube al que autorizar.

No compartas contraseñas ni pegues claves en el código o en el chat.

## Configuración desde Android
1. En GitHub, crea un repositorio **público** llamado `youtube-short-pilot` (los minutos estándar de GitHub Actions son gratuitos en repositorios públicos). El código no contiene secretos; no publiques nunca tokens ni claves.
2. Sube todos los archivos de esta carpeta conservando las rutas, usando **Add file → Upload files** en el navegador.
3. En Pexels API, crea una clave y copia el valor.
4. En Google Cloud Console crea un proyecto, habilita **YouTube Data API v3** y configura la pantalla de consentimiento OAuth. Crea credenciales OAuth.
5. Consigue un refresh token usando el flujo OAuth oficial de Google con tu propio cliente y el scope `youtube.upload`. Guarda el refresh token en un lugar privado. No uses un token de terceros.
6. En el repo GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Añade:
   - `PEXELS_API_KEY`
   - `YT_CLIENT_ID`
   - `YT_CLIENT_SECRET`
   - `YT_REFRESH_TOKEN`
7. Ve a **Actions → Build and upload pilot Short → Run workflow**.
8. Mira los logs. Si termina bien, el video aparecerá en YouTube Studio como privado. Revisa el video antes de cambiar su visibilidad.

## OAuth: advertencia importante
La generación de refresh token es el paso más delicado desde un teléfono. Google cambia el flujo según el tipo de cliente y el estado de verificación. Si el proyecto OAuth está en modo de prueba, los refresh tokens pueden caducar; agrega tu cuenta como usuario de prueba. No compartas el secreto del cliente ni el refresh token.

## Para pasar a cinco canales
Cada canal necesita autorización propia y un refresh token propio. Se agregaría una configuración por canal y se ejecutaría un job por canal. No lo actives hasta probar que el piloto funciona y comprobar que los videos son adecuados y cumplen los derechos/licencias.

## Fuentes oficiales
- YouTube upload API: https://developers.google.com/youtube/v3/docs/videos/insert
- YouTube API upload guide: https://developers.google.com/youtube/v3/guides/uploading_a_video
- Pexels API docs: https://www.pexels.com/api/documentation/
- GitHub Actions billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- YouTube monetization policies: https://support.google.com/youtube/answer/1311392

## Nota de licencia y calidad
El código agrega la URL del video y el nombre del contribuyente de Pexels a la descripción. Revisa la licencia vigente y las condiciones de uso de la API. El TTS depende de un servicio online de terceros y puede cambiar o dejar de funcionar. Un video automatizado con stock y voz sintética no garantiza elegibilidad para monetización; añade investigación, análisis y valor original sustancial.
