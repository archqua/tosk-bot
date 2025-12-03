import unittest


class FailingTests(unittest.TestCase):
    def test_fail_with_assert(self):
        # This test will fail because the assertion is False
        self.assertTrue(False, "This test fails because the assertion is False")

    def test_fail_with_exception(self):
        # This test will fail due to an exception raised explicitly
        raise Exception("This test fails by raising an exception")

    def test_fail_with_self_fail(self):
        # This test will also fail using the built-in fail method
        self.fail("This test fails because it calls self.fail()")


if __name__ == "__main__":
    unittest.main()
