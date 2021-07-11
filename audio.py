import fire
import uuid
import zipfile
import asyncio
import shutil
import pathlib
from typing import List, Tuple, Optional
import os


def probe_files(src: list) -> List[list]:
    files = []
    for f in os.listdir(os.path.join(*src)):
        if f[0] == '.':
            continue
        path = [*src, f]
        if os.path.isdir(os.path.join(*path)):
            files = [*files, *probe_files(path)]
        else:
            if isinstance(f, str) and f.split('.')[-1] in ('mp3', 'zip'):
                files.append(path)
    return files


def trans_zip(src: List[str], dst: List[str]):
    dst[-1] = '.'.join(dst[-1].split('.')[:-1])
    cache_dir = os.path.join(dst[0], '.cache', str(uuid.uuid4()))
    try:
        print("TransZip: {} => {}".format(os.path.join(*src[1:]), os.path.join(*dst[1:])))
        with zipfile.ZipFile(os.path.join(*src), 'r') as z:
            for fn in z.namelist():
                fn = z.extract(fn, cache_dir)
                extracted_path = pathlib.Path(fn)
                for e in ('cp437',):
                    try:
                        extracted_path.rename(fn.encode(e).decode('gbk', 'ignore'))
                        break
                    except UnicodeEncodeError as ex:
                        print(ex)
        subs = []
        for f in os.listdir(cache_dir):
            try:
                f.encode('gbk')
            except UnicodeEncodeError:
                continue
            subs.append([cache_dir, f])
        dst = os.path.join(*dst)
        os.makedirs(dst, 0o755, True)
        if len(subs) == 1:
            # 省略一级目录
            transcode(os.path.join(*subs[0]), dst)
        else:
            transcode(cache_dir, dst)
    finally:
        shutil.rmtree(cache_dir)


def trans(src: List[str], dst: List[str]) -> Optional[Tuple[str, str]]:
    ext = src[-1].split('.')[-1]
    if ext in ('zip', ):
        trans_zip(src, dst)
        return None
    else:
        print("TransCode: {} => {}".format(os.path.join(*src[1:]), os.path.join(*dst[1:])))
        _src = os.path.join(*src)
        _dst = os.path.join(*dst)
        if not os.path.exists(_src):
            raise FileNotFoundError(_src)
        os.makedirs(os.path.join(*dst[:-1]), 0o755, True)
        return _src, _dst


def transcode(src: str, dst: str):
    """音频批量转码"""
    if not os.path.exists(src):
        raise FileNotFoundError(src)
    src = os.path.relpath(src)
    if not os.path.exists(dst) or not os.access(dst, os.W_OK):
        raise FileNotFoundError(dst)

    jobs = []
    files = probe_files([src])
    for f in files:
        _ = trans(f, [dst, *f[1:]])
        if _ is not None:
            jobs.append(_)
    asyncio.get_event_loop().run_until_complete(run_jobs(jobs))


async def _trans(src: str, dst: str):
    args = ('-y', '-v', '0', '-nostats', '-i', src,
            '-vn', '-map_metadata', '-1', '-c:a', 'libmp3lame', '-ac', '1', '-b:a', '32000', '-ar', '22050',
            dst)
    _ = await asyncio.create_subprocess_exec('/usr/bin/ffmpeg', *args)
    await _.wait()


async def run_jobs(jobs: List[Tuple[str, str]]):
    """
    ffmpeg -i '{}' -vn -map_metadata -1 -c:a libmp3lame -ac 1 -b:a 32000 -ar 22050 '{}'
    :param jobs:
    :return:
    """
    tasks = []
    for j in jobs:
        tasks.append(asyncio.create_task(_trans(*j)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    fire.Fire(transcode)
