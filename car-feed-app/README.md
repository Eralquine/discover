# CarFeed

App Android para reproducir un feed vertical de videos en la pantalla de un
auto (radio/head unit con Android), navegable con los botones físicos de
**volumen arriba / volumen abajo** en vez de tocar la pantalla.

## Por qué no es "TikTok" literal

TikTok no publica una API para su feed "Para ti", y replicarlo requeriría
scrapear/imitar su API privada, algo que viola sus Términos de Servicio.
Por eso esta app no se conecta a TikTok: reproduce **tus propios videos
verticales** (los que subas al dispositivo), con la misma mecánica de swipe
vertical que un feed tipo TikTok/Reels.

Si más adelante querés sumar contenido público de TikTok de forma legítima,
la vía es su [oEmbed API](https://www.tiktok.com/oembed) video por video
(no da un feed navegable), o pedir acceso a la TikTok Content Posting/Display
API oficial.

## Cómo funciona

- `MainActivity` muestra un `ViewPager2` en orientación **vertical** a
  pantalla completa.
- `dispatchKeyEvent` intercepta `KEYCODE_VOLUME_UP` / `KEYCODE_VOLUME_DOWN`
  antes de que el sistema los use para subir/bajar volumen, y en cambio
  mueve el `ViewPager2` al video anterior/siguiente (`pager.currentItem ± 1`).
- `VideoFeedAdapter` crea un `ExoPlayer` (Media3) por video visible y lo
  libera cuando la vista se recicla.
- `VideoRepository` lee, vía `MediaStore`, los videos que estén en la
  carpeta del dispositivo `Movies/CarFeed`.

## Uso

1. Copiá tus clips verticales (mp4) a `Movies/CarFeed` en el dispositivo
   (por USB, o con cualquier explorador de archivos).
2. Compilá e instalá la app (Android Studio, o `./gradlew installDebug`
   generando primero el wrapper con `gradle wrapper` si no está presente).
3. Abrí la app: reproduce el primer video en loop automáticamente.
4. Usá el botón/rueda de volumen del auto: **abajo** pasa al siguiente
   video, **arriba** vuelve al anterior. El volumen del sistema no cambia
   mientras la app está en primer plano.

## Nota de seguridad

Se dejó **sin restricción de manejo** a pedido explícito: la app reproduce
video sin chequear si el vehículo está en movimiento. Muchos sistemas
(Android Auto, Android Automotive OS) bloquean video mientras se maneja
precisamente porque es una distracción seria. Si en algún momento se quiere
agregar esa protección, el punto de enganche es `MainActivity.loadFeed()`:
ahí se podría consultar un sensor/servicio de velocidad del vehículo y
pausar el `ViewPager2`/`ExoPlayer` cuando el auto esté en movimiento.

## Estructura

```
car-feed-app/
  app/
    src/main/java/com/carfeed/app/
      MainActivity.kt        # pantalla completa + swipe por volumen
      VideoFeedAdapter.kt     # feed vertical con ExoPlayer
      VideoRepository.kt      # lee videos locales desde MediaStore
    src/main/res/...
  build.gradle.kts / settings.gradle.kts
```
