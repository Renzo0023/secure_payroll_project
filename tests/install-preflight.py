#!/usr/bin/env python3
"""Refus précoces de l'installateur : AppArmor, PHP incomplet, essai antérieur. Aucun MySQL démarré."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PHP = shutil.which('php')


def check(ok, label):
    if not ok:
        sys.exit('FAIL ' + label)
    print('PASS ' + label)


def script(path, body):
    path.write_text('#!/bin/sh\n' + body + '\n')
    path.chmod(0o700)


with tempfile.TemporaryDirectory(prefix='securepayroll-preflight-') as temporary:
    base = Path(temporary).resolve()
    tools = base / 'bin'
    tools.mkdir()
    target = base / 'local'
    script(tools / 'mysql', 'exit 1')
    # mysqld 8.4 factice, refusé en écriture : ni datadir ni journal (comportement sous AppArmor).
    script(tools / 'mysqld', 'case "$*" in *--version*) echo "mysqld Ver 8.4.13";; *) exit 1;; esac')
    script(tools / 'php', 'exec ' + PHP + ' "$@"')

    def install():
        return subprocess.run([sys.executable, str(ROOT / 'bin/init-local.py'), '--directory', str(target)],
                              env={**os.environ, 'PATH': str(tools) + ':' + os.environ['PATH']},
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)

    for attempt in ('premier essai', 'relance immédiate'):
        result = install()
        check(result.returncode == 1 and 'ne peut pas écrire dans ' + str(target) in result.stderr,
              'Écriture refusée signalée (' + attempt + ')')
        check(not target.exists(), 'Aucun répertoire ni secret laissé (' + attempt + ')')
    if Path('/etc/apparmor.d/usr.sbin.mysqld').is_file():
        check(str(target) + ' | sudo tee -a' in result.stderr
              and 'init-local.py --directory ' + str(target) in result.stderr,
              'Commandes AppArmor exactes pour le répertoire demandé')

    # Échec ayant produit un journal : tout est conservé pour diagnostic.
    script(tools / 'mysqld', 'case "$*" in *--version*) echo "mysqld Ver 8.4.13";; '
           '*) echo erreur > ' + str(target / 'initialize.log') + '; exit 1;; esac')
    result = install()
    check(result.returncode == 1 and 'répertoire conservé' in result.stderr
          and (target / 'initialize.log').is_file() and not (target / 'credentials.json').exists(),
          'Échec avec journal : répertoire conservé, aucun secret créé')
    shutil.rmtree(target)

    # Reste d'un refus avec l'ancien installateur : secrets sans datadir.
    target.mkdir(mode=0o700)
    (target / 'credentials.json').write_text('{}')
    result = install()
    check(result.returncode == 1 and 'Essai antérieur interrompu' in result.stderr
          and (target / 'credentials.json').exists(), 'Essai antérieur expliqué, jamais supprimé')
    (target / 'data').mkdir()
    result = install()
    check(result.returncode == 1 and 'Répertoire déjà présent' in result.stderr, 'Datadir existant : refus inchangé')
    shutil.rmtree(target)

    # PHP sans extension chargée (php -n) : refus avant toute écriture.
    script(tools / 'php', 'exec ' + PHP + ' -n "$@"')
    result = install()
    check(result.returncode == 1 and 'PHP incomplet' in result.stderr and 'mbstring' in result.stderr
          and not target.exists(), 'Extensions PHP absentes : refus avant toute écriture')
