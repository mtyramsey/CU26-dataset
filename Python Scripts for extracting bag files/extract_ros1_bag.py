#!/usr/bin/env python3
import os
import argparse
from pathlib import Path

import rosbag
from cv_bridge import CvBridge
import cv2
import sensor_msgs.point_cloud2 as pc2


def write_xyzi_as_text_pcd(msg, out_path):
    points = []
    for p in pc2.read_points(msg, field_names=("x", "y", "z", "intensity"), skip_nans=True):
        points.append(p)

    with open(out_path, "w") as f:
        f.write("FIELDS x y z intensity\n")
        for x, y, z, intensity in points:
            f.write(f"{x} {y} {z} {intensity}\n")


def write_timestamp(ts, out_path):
    with open(out_path, "w") as f:
        f.write(f"{ts:.9f}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", required=True, help="Path to ROS1 .bag file")
    parser.add_argument("--output", required=True, help="Output folder")
    parser.add_argument("--lidar_topic", required=True)
    parser.add_argument("--primary_topic", required=True)
    parser.add_argument("--secondary_topic", required=True)
    args = parser.parse_args()

    bag_path = Path(args.bag)
    out_root = Path(args.output)

    lidar_dir = out_root / "lidar"
    primary_dir = out_root / "primary_camera"
    secondary_dir = out_root / "secondary_camera"

    lidar_dir.mkdir(parents=True, exist_ok=True)
    primary_dir.mkdir(parents=True, exist_ok=True)
    secondary_dir.mkdir(parents=True, exist_ok=True)

    bridge = CvBridge()

    lidar_idx = 0
    primary_idx = 0
    secondary_idx = 0

    with rosbag.Bag(str(bag_path), "r") as bag:
        for topic, msg, t in bag.read_messages(topics=[
            args.lidar_topic,
            args.primary_topic,
            args.secondary_topic
        ]):
            ts = t.to_sec()

            if topic == args.lidar_topic:
                stem = f"frame_{lidar_idx:06d}"
                write_xyzi_as_text_pcd(msg, lidar_dir / f"{stem}.pcd")
                write_timestamp(ts, lidar_dir / f"{stem}_timestamp.txt")
                lidar_idx += 1

            elif topic == args.primary_topic:
                stem = f"frame_{primary_idx:06d}"
                img = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
                cv2.imwrite(str(primary_dir / f"{stem}.png"), img)
                write_timestamp(ts, primary_dir / f"{stem}_timestamp.txt")
                primary_idx += 1

            elif topic == args.secondary_topic:
                stem = f"frame_{secondary_idx:06d}"
                img = bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
                cv2.imwrite(str(secondary_dir / f"{stem}.png"), img)
                write_timestamp(ts, secondary_dir / f"{stem}_timestamp.txt")
                secondary_idx += 1

    print(f"Done.")
    print(f"Lidar frames: {lidar_idx}")
    print(f"Primary frames: {primary_idx}")
    print(f"Secondary frames: {secondary_idx}")
    print(f"Saved to: {out_root}")


if __name__ == "__main__":
    main()
