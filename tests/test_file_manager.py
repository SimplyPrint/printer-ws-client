import time
import unittest

from simplyprint_ws_client.helpers.file_manager import File, FileManager

test_time = int(time.time())


def test_files(): return [
    File("test1.gcode", 100, last_modified=test_time - 1000),
    File("test2.gcode", 200, last_modified=test_time - 2000),
    File("test3.gcode", 300, last_modified=test_time - 3000),
    File("test4.gcode", 400, last_modified=test_time - 4000),
    File("test5.gcode", 500, last_modified=test_time - 5000),
]


class TestFileManager(unittest.TestCase):
    def test_file_manager(self):
        fm = FileManager(max_age=1001, max_count=2,
                         max_size=250, least_remaining_space_percentage=0.1)
        files_to_remove = list(
            fm.get_files_to_remove(test_files(), 2000, 1500))

        self.assertEqual(files_to_remove, [
            File("test2.gcode", 200, last_modified=test_time - 2000),
            File("test3.gcode", 300, last_modified=test_time - 3000),
            File("test4.gcode", 400, last_modified=test_time - 4000),
            File("test5.gcode", 500, last_modified=test_time - 5000),
        ])

    def test_file_manager_max_age(self):
        fm = FileManager(max_age=1001, max_count=0,
                         max_size=0, least_remaining_space_percentage=0)
        files_to_remove = list(
            fm.get_files_to_remove(test_files(), 2000, 1500))
        self.assertEqual(files_to_remove, [
            File("test2.gcode", 200, last_modified=test_time - 2000),
            File("test3.gcode", 300, last_modified=test_time - 3000),
            File("test4.gcode", 400, last_modified=test_time - 4000),
            File("test5.gcode", 500, last_modified=test_time - 5000),
        ])

    def test_file_manager_max_count(self):
        fm = FileManager(max_age=0, max_count=2, max_size=0,
                         least_remaining_space_percentage=0)
        files_to_remove = list(
            fm.get_files_to_remove(test_files(), 2000, 1500))

        self.assertEqual(files_to_remove, [
            File("test5.gcode", 500, last_modified=test_time - 5000),
            File("test4.gcode", 400, last_modified=test_time - 4000),
            File("test3.gcode", 300, last_modified=test_time - 3000),
        ])

    def test_file_manager_max_size(self):
        fm = FileManager(max_age=0, max_count=0, max_size=250,
                         least_remaining_space_percentage=0)
        files_to_remove = list(
            fm.get_files_to_remove(test_files(), 2000, 1500))

        self.assertEqual(files_to_remove, [
            File("test3.gcode", 300, last_modified=test_time - 3000),
            File("test4.gcode", 400, last_modified=test_time - 4000),
            File("test5.gcode", 500, last_modified=test_time - 5000),
        ])

    def test_file_manager_least_remaining_space_percentage(self):
        fm = FileManager(max_age=0, max_count=0, max_size=0,
                         least_remaining_space_percentage=1)
        files_to_remove = list(
            fm.get_files_to_remove(test_files(), 2000, 1500))
        self.assertEqual(files_to_remove, list(reversed(test_files())))


if __name__ == '__main__':
    unittest.main()
