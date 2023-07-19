from simplyprint_ws.printer import *

def pop_events(x):
    events = list(x._build_events())

    for event in events:
        print(event.generate())


if __name__ == '__main__':
    tool_temperatures = [
        Temperature(actual=10, target=20),
        Temperature(actual=30, target=40),
    ]

    x = PrinterState(
        tool_temperatures=tool_temperatures,
        bed_temperature=Temperature(actual=10, target=20),
        info=PrinterInfoData(),
        firmware=PrinterFirmware(),
        cpu_info=CpuInfoState(),
        job_info=JobInfoState()
    )

    x.info.api = "2"
    x.info.api_version = "1.0.0"
    x.firmware.name = "Klipper 3"
    x.firmware.version = "1.0.0"
    x.firmware.link = "yay"
    x.firmware.date = "today"

    x.firmware.severity = "warning"
    x.firmware.check_name = "test"
    x.firmware.warning_type = "test"
    x.firmware.url = "test"

    x.cpu_info.temp = 10

    x.cpu_info.temp = 20

    x.status = PrinterStatus.PRINTING

    x.bed_temperature.actual = 11
    x.bed_temperature.target = 12

    pop_events(x)

    x.tool_temperatures[0].actual = 11

    pop_events(x)