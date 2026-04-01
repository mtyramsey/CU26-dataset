#!/usr/bin/env python3
import os
import io
import argparse
import numpy as np

import rosbag
from cv_bridge import CvBridge
import cv2

from sensor_msgs.msg import PointCloud2, Image, CompressedImage
import sensor_msgs.point_cloud2 as pc2


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def write_text(path, text):
    with open(path, "w") as f:
        f.write(str(text) + "\n")


def sanitize_topic(topic):
    return topic.strip("/").replace("/", "_")


def get_msg_timestamp(msg, fallback_t):
    # Prefer message header stamp when present, otherwise bag timestamp
    if hasattr(msg, "header") and hasattr(msg.header, "stamp"):
        try:
            return msg.header.stamp.to_sec()
        except Exception:
            pass
    return fallback_t.to_sec()


def pointcloud2_to_xyz_intensity(msg):
    # Read x,y,z and intensity if present
    field_names = [f.name for f in msg.fields]
    has_intensity = "intensity" in field_names

    if has_intensity:
        points = list(
            pc2.read_points(
                msg,
                field_names=("x", "y", "z", "intensity"),
                skip_nans=True
            )
        )
        if len(points) == 0:
            return np.empty((0, 3), dtype=np.float32), np.empty((0,), dtype=np.float32)
        arr = np.array(points, dtype=np.float32)
        xyz = arr[:, :3]
        intensity = arr[:, 3]
    else:
        points = list(
            pc2.read_points(
                msg,
                field_names=("x", "y", "z"),
                skip_nans=True
            )
        )
        if len(points) == 0:
            return np.empty((0, 3), dtype=np.float32), np.empty((0,), dtype=np.float32)
        xyz = np.array(points, dtype=np.float32)
        intensity = np.zeros((xyz.shape[0],), dtype=np.float32)

    return xyz, intensity


def write_pcd_ascii(filepath, xyz, intensity):
    n = xyz.shape[0]
    with open(filepath, "w") as f:
        f.write("# .PCD v0.7 - Point Cloud Data file format\n")
        f.write("VERSION 0.7\n")
        f.write("FIELDS x y z intensity\n")
        f.write("SIZE 4 4 4 4\n")
        f.write("TYPE F F F F\n")
        f.write("COUNT 1 1 1 1\n")
        f.write(f"WIDTH {n}\n")
        f.write("HEIGHT 1\n")
        f.write("VIEWPOINT 0 0 0 1 0 0 0\n")
        f.write(f"POINTS {n}\n")
        f.write("DATA ascii\n")
        for i in range(n):
            f.write(f"{xyz[i,0]} {xyz[i,1]} {xyz[i,2]} {intensity[i]}\n")


def save_image(msg, out_png):
    if isinstance(msg, Image):
        bridge = CvBridge()
        cv_img = bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")

        # Convert grayscale/BGR/BGRA safely for PNG writing
        if len(cv_img.shape) == 2:
            img_to_save = cv_img
        elif cv_img.shape[2] == 3:
            # ROS/OpenCV is usually BGR already; cv2.imwrite expects BGR
            img_to_save = cv_img
        elif cv_img.shape[2] == 4:
            img_to_save = cv_img
        else:
            raise RuntimeError("Unsupported image shape")
        cv2.imwrite(out_png, img_to_save)

    elif isinstance(msg, CompressedImage):
        np_arr = np.frombuffer(msg.data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)
        cv2.imwrite(out_png, img)
    else:
        raise RuntimeError("Unsupported image message type")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", required=True, help="Path to .bag file")
    parser.add_argument("--lidar-topic", default="/velodyne_points")
    parser.add_argument("--primary-topic", default="/camera_primary/image_raw")
    parser.add_argument("--secondary-topic", default="/camera_secondary/image_raw")
    parser.add_argument("--out", default="exported_data")
    args = parser.parse_args()

    out_root = args.out
    lidar_dir = os.path.join(out_root, "lidar")
    primary_dir = os.path.join(out_root, "camera_primary")
    secondary_dir = os.path.join(out_root, "camera_secondary")

    ensure_dir(lidar_dir)
    ensure_dir(primary_dir)
    ensure_dir(secondary_dir)

    bag = rosbag.Bag(args.bag, "r")

    lidar_idx = 0
    primary_idx = 0
    secondary_idx = 0

    for topic, msg, t in bag.read_messages(topics=[args.lidar_topic, args.primary_topic, args.secondary_topic]):
        ts = get_msg_timestamp(msg, t)
        ts_str = f"{ts:.9f}"

        if topic == args.lidar_topic and isinstance(msg, PointCloud2):
            xyz, intensity = pointcloud2_to_xyz_intensity(msg)

            base = os.path.join(lidar_dir, f"frame_{lidar_idx:06d}")
            write_pcd_ascii(base + ".pcd", xyz, intensity)
            np.savetxt(base + "_intensity.txt", intensity, fmt="%.6f")
            write_text(base + "_timestamp.txt", ts_str)
            lidar_idx += 1

        elif topic == args.primary_topic:
            base = os.path.join(primary_dir, f"frame_{primary_idx:06d}")
            save_image(msg, base + ".png")
            write_text(base + "_timestamp.txt", ts_str)
            primary_idx += 1

        elif topic == args.secondary_topic:
            base = os.path.join(secondary_dir, f"frame_{secondary_idx:06d}")
            save_image(msg, base + ".png")
            write_text(base + "_timestamp.txt", ts_str)
            secondary_idx += 1

    bag.close()

    print("Done.")
    print(f"Lidar frames: {lidar_idx}")
    print(f"Primary camera frames: {primary_idx}")
    print(f"Secondary camera frames: {secondary_idx}")


if __name__ == "__main__":
    main()
