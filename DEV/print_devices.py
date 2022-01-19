
import pyaudio
p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')
for i in range(0, numdevices):
    # if 0 < p.get_device_info_by_host_api_device_index(0, i).get("maxInputChannels"):
    #     print("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get("name"))
    # if 0 < p.get_device_info_by_host_api_device_index(0, i).get("maxOutputChannels"):
    #     print("Output Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get("name"))
    device = p.get_device_info_by_host_api_device_index(0, i)
    device_name = p.get_device_info_by_host_api_device_index(0, i).get("name")
    if device.get("maxInputChannels") > 0:
        print("Input Device id ", i, " - ", device_name)
    if device.get("maxOutputChannels") > 0:
        print("Output Device id ", i, " - ", device_name)
