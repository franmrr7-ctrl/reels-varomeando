"""Efectos de sonido sintetizados por codigo (sin derechos): whoosh de transicion, pop de texto y ding final."""
import wave

import numpy as np

SR = 44100


def _whoosh(n_s=0.38, vol=0.30):
    n = int(SR * n_s)
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n)
    # filtro paso-banda barrido: media movil cuya longitud baja (el tono sube)
    out = np.zeros(n)
    k = np.cumsum(noise)
    for i in range(n):
        w = max(2, int(120 - 100 * i / n))
        out[i] = (k[i] - k[max(0, i - w)]) / w
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    out = out * env
    return vol * out / (np.abs(out).max() + 1e-9)


def _pop(vol=0.28):
    n = int(SR * 0.12)
    t = np.arange(n) / SR
    f = 520 * np.exp(-t * 18) + 180
    ph = 2 * np.pi * np.cumsum(f) / SR
    return vol * np.sin(ph) * np.exp(-t * 32)


def _ding(vol=0.22):
    n = int(SR * 1.1)
    t = np.arange(n) / SR
    s = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * d)
            for f, a, d in ((1318, 1.0, 4.0), (1976, 0.45, 5.5), (2637, 0.25, 7.0)))
    s[:int(SR * 0.004)] *= np.linspace(0, 1, int(SR * 0.004))
    return vol * s / np.abs(s).max()


def make_sfx(path, offsets, total):
    """offsets: segundo de inicio de cada escena. Whoosh antes de cada corte, pop al aparecer el texto, ding al final."""
    buf = np.zeros(int(SR * (total + 1.0)))

    def put(sig, at):
        i = max(0, int(SR * at))
        buf[i:i + len(sig)] += sig[:max(0, len(buf) - i)]

    wh, pp = _whoosh(), _pop()
    for k, o in enumerate(offsets):
        if k > 0:
            put(wh, o - 0.22)
        put(pp, o + 0.12)
    put(_ding(), offsets[-1] + 0.55)
    buf = np.clip(buf, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((buf * 32767).astype("<i2").tobytes())
