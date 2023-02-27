#! /usr/bin/env python3
# kinescope-downloader (c) Michael A. Kangin 2022
# License: GPLv2
# Script parameters: <video-id> [video-name]
# video-id looks like '201234567' and can be obtain from browser network console
# (you can filter output for "master.mpd" file).
# This script requires 'ffmpeg' utility

import os
import subprocess
import sys
import urllib.request
from typing import Dict, List

import xmltodict

# These constants can be re-assign from environments
BASEURL = "https://kinescope.io"
AUDIO_CHUNK_SEGMENTS = 200
VIDEO_CHUNK_SEGMENTS = 100
SAFE_CHUNK_LEN = 24000000
REFERER = BASEURL
DEBUG = 0


def err_exit(err_msg: str) -> None:
    raise SystemExit(f"Error: {err_msg}")


def get_media_byte_range(
        req: urllib.request.Request,
        from_b: int,
        to_b: int,
        first_seg: int,
        last_seg: int,
        total_segs: int,
        debug: bool = False) -> bytes:
    # print some progress info, apply actual 'Range' header to request object and download the segment
    info_out = f"Media segment: {last_seg + 1}/{total_segs} ({(last_seg + 1) / total_segs * 100:2.2f}%) "
    debug_out = f"Media segment: {first_seg + 1}-{last_seg + 1}/{total_segs}\t({last_seg - first_seg + 1})" \
                f"\tbytes={from_b}-{to_b}\tsize={to_b - from_b + 1}"
    if debug:
        print(debug_out)
    else:
        print(info_out, end="\r")

    req.add_header('Range', f"bytes={from_b}-{to_b}")
    res = urllib.request.urlopen(req).read()
    if not isinstance(res, bytes):
        raise TypeError
    return res


def get_segments(
        req: urllib.request.Request,
        segments: List[Dict[str, str]],
        chunk: int,
        safe_chunk_len: int,
        debug: bool) -> bytes:
    # will try to combine a few (*_CHUNK_SEGMENTS) segments to download together
    # it will significantly improve speed
    media = b''
    seg_pointer = 0
    total_segments = len(segments)

    while seg_pointer < total_segments:
        seg_url = segments[seg_pointer]["@media"]
        # recreate request object if the URL of the next segment is different.
        if seg_url != req.full_url:
            req = urllib.request.Request(seg_url)

        # start download chunk from this segment number
        seg_from = seg_pointer
        # start byte offset of this chunk
        offs_a = int(segments[seg_from]["@mediaRange"].split('-')[0])

        # check all segments in the chunk.
        # if the next segment has another URL, or chunk size exceeds SAFE_CHUNK_LEN, we'll start a new chunk.
        for seg_idx in range(seg_pointer, seg_pointer + chunk):
            # finish this chunk if we reach the last segment or if next segment has another URL
            if seg_pointer >= total_segments or seg_url != segments[seg_idx]["@media"]:
                break

            # end byte offset for current chunk
            offs_b = int(segments[seg_idx]["@mediaRange"].split('-')[1])

            # finish this chunk if chunk byte size exceeds SAFE_CHUNK_LEN
            if offs_b - offs_a + 1 > safe_chunk_len:
                break

            # if all checks pass, add this segment to the chunk and switch pointer to the next segment
            seg_pointer += 1

        # final end byte offset for this chunk
        offs_b = int(segments[seg_pointer - 1]["@mediaRange"].split('-')[1])

        # download the chunk
        media += get_media_byte_range(req, offs_a, offs_b, seg_from, seg_pointer - 1, total_segments, debug)

    print("")
    return media


def main() -> None:
    # ========== start here ===========
    # initialization and configuration
    video_id = ''
    video_name = ''

    try:
        video_id = sys.argv[1]
    except IndexError:
        err_exit("Please provide video ID")

    try:
        video_name = sys.argv[2]
    except IndexError:
        video_name = video_id

    baseurl = os.getenv("BASEURL", BASEURL)
    debug = bool(int(os.getenv("DEBUG", str(DEBUG))))
    audio_chunk_segments = int(os.getenv("AUDIO_CHUNK_SEGMENTS", str(AUDIO_CHUNK_SEGMENTS)))
    video_chunk_segments = int(os.getenv("VIDEO_CHUNK_SEGMENTS", str(VIDEO_CHUNK_SEGMENTS)))
    safe_chunk_len = int(os.getenv("SAFE_CHUNK_LEN", str(SAFE_CHUNK_LEN)))
    referer = os.getenv("REFERER", REFERER)

    # obtain XML with video segments description
    print("Get video description... ", end='')
    mpd_req = urllib.request.Request(f"{baseurl}/{video_id}/master.mpd")
    mpd_req.add_header('Referer', referer)
    mpd_raw = urllib.request.urlopen(mpd_req).read()

    # or can be read from file
    # with open("master.mpd", 'r') as f:
    #     mpd_raw = f.read()

    # parse XML into internal object
    mpd = xmltodict.parse(mpd_raw)
    print("Done.\n")

    # To get any media segment, we need provide its URL and 'Range' header
    # this info present in XML description

    # mpd['MPD']['Period']['AdaptationSet'][0]["Representation"] - array of video streams with different resolutions
    # mpd['MPD']['Period']['AdaptationSet'][1]["Representation"] - the only audio stream

    # the first media segment described in ["SegmentList"]["Initialization"] field
    # all others - array of URL/range pairs at ["SegmentList"]["SegmentURL"]

    adapt_set = mpd['MPD']['Period']['AdaptationSet']

    # Download audio stream
    print("Get audio stream...")
    # First, we are prepare to download init segment for this stream
    audio_url = adapt_set[1]["Representation"]["SegmentList"]["Initialization"]["@sourceURL"]
    bytes_range = adapt_set[1]["Representation"]["SegmentList"]["Initialization"]["@range"]
    # create request object
    audio_req = urllib.request.Request(audio_url)
    # add actual Range header
    audio_req.add_header('Range', f"bytes={bytes_range}")
    # download init segment
    audio = urllib.request.urlopen(audio_req).read()
    # Download all other segments for this stream
    audio += get_segments(
        audio_req,
        adapt_set[1]["Representation"]["SegmentList"]["SegmentURL"],
        audio_chunk_segments,
        safe_chunk_len,
        debug
    )

    # Save audio stream in temporary file
    with open(f"{video_id}.audio", "wb") as file_:
        file_.write(audio)
    print("Audio stream done.\n")

    # Download video stream
    print("Get video stream...")
    # get the best available resolution
    max_width = int(adapt_set[0]["@maxWidth"])

    video = b''
    for video_stream in adapt_set[0]["Representation"]:
        # skip low resolution video streams
        if int(video_stream["@width"]) < max_width:
            continue

        video_url = video_stream["SegmentList"]["Initialization"]["@sourceURL"]
        bytes_range = video_stream["SegmentList"]["Initialization"]["@range"]
        video_req = urllib.request.Request(video_url)
        video_req.add_header('Range', f"bytes={bytes_range}")
        video = urllib.request.urlopen(video_req).read()
        video += get_segments(
            video_req,
            video_stream["SegmentList"]["SegmentURL"],
            video_chunk_segments,
            safe_chunk_len,
            debug
        )
        # we need only one video stream
        break

    # save video stream in temporary file
    with open(f"{video_id}.video", "wb") as file_:
        file_.write(video)
    print("Video stream done.\n")

    # Combine audio and video streams in one ready-to-play MP4 container
    convert_cmd = f"ffmpeg -y -i {video_id}.video -i {video_id}.audio -c copy -bsf:a aac_adtstoasc '{video_name}.mp4'"
    print("Converting video file... ", end='')
    sys.stdout.flush()
    run_res = subprocess.run(convert_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if run_res.returncode:
        err_exit(f"Error video convert invocation: {run_res.stderr.decode()}")
    else:
        os.unlink(f"{video_id}.audio")
        os.unlink(f"{video_id}.video")
        print(f"Done: {video_name}.mp4")


if __name__ == '__main__':
    main()
