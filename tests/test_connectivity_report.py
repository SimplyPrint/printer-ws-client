from simplyprint_ws_client.shared.debug.connectivity import ConnectivityReport


def test_generate_default_report():
    ConnectivityReport.generate_default()
