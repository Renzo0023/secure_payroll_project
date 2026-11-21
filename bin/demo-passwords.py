#!/usr/bin/env python3
"""Retrieve generated presentation passwords once, in the user's own terminal."""
import json
import os
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        raise RuntimeError('Use your own interactive Ubuntu terminal; never redirect these passwords.')
    pointer=ROOT/'storage/logs/demo-credentials.json'
    info=json.loads(pointer.read_text())
    path=Path(info['socket'])
    if path.parent.stat().st_uid!=os.getuid() or path.parent.stat().st_mode&0o077:
        raise RuntimeError('Private credential socket required.')
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(10);client.connect(str(path));client.sendall(b'RETRIEVE-ONCE\n')
        chunks=[]
        while True:
            chunk=client.recv(8192)
            if not chunk:break
            chunks.append(chunk)
    secrets=json.loads(b''.join(chunks))
    print('Mots de passe temporaires — affichage unique, aucun fichier en clair :')
    for login,password in sorted(secrets.items()):print(login+' : '+password)
    print('Conservez-les maintenant dans votre gestionnaire privé. Ils ne seront plus récupérables ici.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError) as error:
        print(str(error) if isinstance(error,RuntimeError) else 'Secrets déjà récupérés, expirés ou indisponibles.',file=sys.stderr);sys.exit(1)
