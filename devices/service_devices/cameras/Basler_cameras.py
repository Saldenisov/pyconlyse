"""
Controllers of Basler cameras are described here

created
"""
from dataclasses import asdict
from distutils.util import strtobool
import numpy
from pypylon import pylon, genicam
from datetime import datetime
from time import sleep

from communication.messaging.messages import *
from devices.service_devices.cameras.camera_controller import CameraController, CameraError
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.myfunc import error_logger, info_msg


class CameraCtrl_Basler(CameraController):
    """
    Works only for GiGE cameras of Basler, usb option is not available
    """

    def __init__(self, **kwargs):
        kwargs['camera_class'] = CameraBasler
        super().__init__(**kwargs)
        self.tl_factory = None
        self.pylon_cameras = None
        self._images_demanders = {}
        self._last_image = None

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        if self.device_status.power:
            if flag:
                res, comments = self._form_devices_list()
            else:
                res, comments = self._release_hardware()
            self.device_status.connected = flag
        else:
            res, comments = False, f'Power is off, connect to controller function cannot be called with flag {flag}'

        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        return super(CameraCtrl_Basler, self)._check_if_active()

    def _check_if_connected(self) -> Tuple[bool, str]:
        pass

    @property
    def cameras(self):
        return self.cameras_no_pylon

    @property
    def cameras_no_pylon(self) -> Dict[int, CameraBasler]:
        cameras = {}
        for camera_id, camera in self._cameras.items():
            cameras[camera_id] = camera.no_pylon()
        return cameras

    def _change_camera_status(self, camera_id: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_camera_flag(flag)
        if res:
            camera = self._cameras[camera_id]
            if camera.status != flag:
                info = ''
                if camera.status == 2 and force:
                    camera.pylon_camera.StopGrabbing()
                    info = f'Camera id={camera_id}, name={camera.friendly_name} was stopped grabbing. {comments}'
                    camera.status = flag
                    res, comments = True, f'Camera id={camera_id}, name={camera.friendly_name} is set to {flag}. {info}'
                elif camera.status == 2 and not force:
                    res, comments = False, f'Camera id={camera_id}, name={camera.friendly_name} is grabbing. ' \
                                           'Force Stop in order to change status.'
                elif flag in [0, 1, 2]:
                    try:
                        if flag == 2 and camera.status == 1:
                            # TODO: must have some other strategies for future
                            camera.pylon_camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                        elif flag == 2 and camera.status == 0:
                            return False, f'First activate camera with camera id={camera_id}, ' \
                                                   f'name={camera.friendly_name}.'
                        if flag == 1:
                            camera.pylon_camera.Open()
                        elif flag == 0:
                            camera.pylon_camera.Close()
                        camera.status = flag
                        res, comments = True, f'Camera id={camera_id}, name={camera.friendly_name} status is set to ' \
                                              f'{flag}. {info}'
                    except pylon.GenericException as e:
                        comments = f'Tried to open connection, but failed: {e}'
                        error_logger(self, self._change_camera_status, comments)
                        return False, comments
            else:
                res, comments = True, f'Camera id={camera_id}, name={camera.friendly_name} is already set to {flag}'
        return res, comments

    def _form_devices_list(self) -> Tuple[bool, str]:
        # Init all camera
        try:
            # Get the transport layer factory.
            self.tl_factory = pylon.TlFactory.GetInstance()
            # Get all attached devices and exit application if no device is found.
            pylon_devices: Tuple[pylon.DeviceInfo] = self.tl_factory.EnumerateDevices()
            if len(pylon_devices) == 0:
                return False, "No cameras present."
            elif len(pylon_devices) != self._cameras_number:
                error_logger(self, self._form_devices_list, f'Not all cameras listed in DB are present.')

            # Create an array of instant cameras for the found devices and avoid exceeding a maximum number of devices.
            self.pylon_cameras: pylon.InstantCameraArray = pylon.InstantCameraArray(min(len(pylon_devices),
                                                                                        self._cameras_number))

            device_id_camera_id = self.device_id_to_id
            keep_camera = []

            for i, pylon_camera in enumerate(self.pylon_cameras):
                pylon_camera.Attach(self.tl_factory.CreateDevice(pylon_devices[i]))
                try:
                    device_id = int(pylon_camera.GetDeviceInfo().GetSerialNumber())
                except ValueError:
                    return False, f'Camera id {pylon_camera.GetDeviceInfo().GetSerialNumber()} ' \
                                  f'was not correctly converted to integer value.'

                if device_id in device_id_camera_id:
                    self._cameras[device_id_camera_id[device_id]].pylon_camera = pylon_camera
                    self._cameras[device_id_camera_id[device_id]].converter = pylon.ImageFormatConverter()
                    self._cameras[device_id_camera_id[device_id]].pylon_camera.Open()
                    self._cameras[device_id_camera_id[device_id]].status = 1

                    # Setting Parameters for the cameras
                    res, comments = self._set_parameters_camera(device_id_camera_id[device_id])
                    if res:
                        keep_camera.append(device_id)
                    else:
                        error_logger(self, self._form_devices_list, f'Parameters for camera with id {device_id} were '
                                                                    f'not set: {comments}. Skipping camera.')
                else:
                    info_msg(self, 'INFO', f'Camera with id: {device_id} is not known. Skipping its initialization.')

            # Deleting those cameras read from DB which were not found by controller.
            for device_id, camera_id in device_id_camera_id.items():
                if device_id not in keep_camera:
                    del self._cameras[camera_id]
            return True, ''
        except (genicam.GenericException, ValueError) as e:
            return False, f"An exception occurred. {e}"

    def _get_cameras_status(self) -> List[int]:
        a = {}
        device_id_camera_id = self.device_id_to_id
        for camera_id, pylon_camera in enumerate(self.pylon_cameras):
            device_id = int(pylon_camera.GetDeviceInfo().GetSerialNumber())
            if pylon_camera.IsOpen():
                a[device_id_camera_id[device_id]] = 1
            else:
                a[device_id_camera_id[device_id]] = 0
        b = list([value for _, value in a.items()])
        return b

    def _get_number_cameras(self):
        if not self.tl_factory:
            self.tl_factory = pylon.TlFactory.GetInstance()
        pylon_devices: Tuple[pylon.DeviceInfo] = self.tl_factory.EnumerateDevices()
        return len(pylon_devices)

    def _grabbing(self, demander_id, n_sec: float):
        sleep(0.1)
        if demander_id in self._images_demanders:
            n_images, image_i, camera_id = self._images_demanders[demander_id]
            while image_i != n_images and self._cameras[camera_id].status == 2:
                image_i += 1
                image = self._read_image(self._cameras[camera_id])
                result = FuncGetImagesOutput(comments='', func_success=True, image=image.tolist(),
                                             timestamp=datetime.timestamp(datetime.now()))
                msg_r = self.generate_msg(msg_com=MsgComExt.DONE_IT, receiver_id=demander_id, func_output=result,
                                          reply_to='delayed_response')
                self.send_msg_externally(msg_r)
                self._last_image = image
                sleep(n_sec)
            del self._images_demanders[demander_id]
            self._change_camera_status(camera_id, flag=1, force=True)

    def _prepare_camera_reading(self, camera_id: int) -> Tuple[bool, str]:
        camera = self._cameras[camera_id]
        if camera.status == 0:
            return False, f'Camera {camera_id} is closed. Activate the camera first to start grabbing.'
        elif camera.status == 1:
            return self._change_camera_status(camera_id, 2)
        elif camera.status == 2:
            return True, 'Already grabbing.'
        else:
            return False, f'Camera {camera_id} has strange status {camera.status}. Internal error.'

    def _read_image(self, camera: CameraBasler) -> numpy.ndarray:
        try:
            if not camera.pylon_camera.IsGrabbing():
                raise CameraError(self, f"Camera {camera.friendly_name} was stopped during grabbing.")
            grabResult = camera.pylon_camera.RetrieveResult(1500, pylon.TimeoutHandling_ThrowException)
            if grabResult.GrabSucceeded():
                # Access the image data
                image = camera.converter.Convert(grabResult)
                grabResult.Release()
                arr = image.GetArray()
                return arr
            else:
                raise pylon.GenericException
        except (pylon.GenericException, pylon.TimeoutException, CameraError) as e:
            error_logger(self, self._read_image, e)
            w = camera.parameters['AOI_Controls'].Width
            h = camera.parameters['AOI_Controls'].Height
            return numpy.random.randn(w, h)

    def _stop_acquisition(self, camera_id: int) -> Tuple[bool, str]:
        try:
            return self._change_camera_status(camera_id, 1, True)
        except pylon.GenericException as e:
            return False, f'While stopping Grabbing of camera {camera_id} error occurred: {e}'

    def _set_private_parameters_db(self):
        self._set_transport_layer_db()
        self._set_analog_controls_db()
        self._set_aoi_controls_db()
        self._set_acquisition_controls_db()
        self._set_image_format_db()

    def _set_analog_controls_db(self):
        self._set_db_attribute(Analog_Controls, self._set_analog_controls_db)

    def _set_acquisition_controls_db(self):
        self._set_db_attribute(Acquisition_Controls, self._set_acquisition_controls_db)

    def _set_aoi_controls_db(self):
        self._set_db_attribute(AOI_Controls, self._set_aoi_controls_db)

    def _set_image_format_db(self):
        self._set_db_attribute(Image_Format_Control, self._set_image_format_db)

    def _set_parameters_camera(self, camera_id: int) -> Tuple[bool, str]:
        device_id: int = self._cameras[camera_id].device_id
        camera = self._cameras[camera_id]
        pylon_camera: pylon.InstantCamera = camera.pylon_camera
        try:
            try:
                friendly_name = eval(self.get_parameters['friendly_names'])[device_id]
            except (KeyError, ValueError, SyntaxError):
                friendly_name = str(device_id)

            pylon_camera.GetDeviceInfo().SetFriendlyName(friendly_name.format('utf-8'))
            camera.friendly_name = friendly_name

            parameters_groups = ['Transport_Layer',
                                 'Analog_Controls',
                                 'AOI_Controls',
                                 'Acquisition_Controls',
                                 'Image_Format_Control']
            for parameters_group_name in parameters_groups:
                if parameters_group_name not in camera.parameters:
                    return False, f'Parameters group "{parameters_group_name}" is absent in DB.'
                else:
                    try:
                        for param_name, param_value in asdict(camera.parameters[parameters_group_name]).items():
                            setattr(camera.pylon_camera, param_name, param_value)
                    except (genicam.GenericException, Exception) as e:
                        raise CameraError(self, text=f'Error appeared: {e} when setting parameter "{param_name}" for '
                                                     f'camera with id {device_id}')

            # setting converter
            # TODO: read values from DB
            camera.converter.OutputPixelFormat = pylon.PixelType_Mono8
            camera.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
            return True, ''
        except (genicam.GenericException, CameraError) as e:
            return False, f'Error appeared when camera id {device_id} was initializing: {e}.'

    def _set_transport_layer_db(self):
        self._set_db_attribute(Transport_Layer, self._set_transport_layer_db)

    def _set_transport_parameters_device(self, func_input: FuncSetTransportParametersInput) -> Tuple[bool, str]:
        # Essential parameters for Basler are Packet size with default value 1500 and Inter-Packet Delay with 1000
        camera_id = func_input.camera_id
        camera: CameraBasler = self._cameras[camera_id]
        packet_size = func_input.packet_size
        inter_packet_delay = func_input.inter_packet_delay
        formed_parameters_dict = {'GevSCPSPacketSize': packet_size, 'GevSCPD': inter_packet_delay}
        if self.device_status.active and camera.pylon_camera.IsOpen() and camera.status != 2:
            try:
                for param_name, param_value in formed_parameters_dict.items():
                    setattr(camera.pylon_camera, param_name, param_value)
                camera.parameters['Transport_Layer'] = Transport_Layer(packet_size, inter_packet_delay)
                return True, ''
            except (genicam.GenericException, Exception) as e:
                return False, f'Error appeared: {e} when setting parameter "{param_name}" for camera with id ' \
                              f'{camera.device_id}.'
        else:
            return False, f'Device_status: {DeviceStatus}, Basler_Camera with id {camera.device_id} connected ' \
                          f'{camera.pylon_camera.IsOpen()}'

    def _set_image_parameters_device(self, func_input: FuncSetImageParametersInput) -> Tuple[bool, str]:
        # Essential parameters for Basler are Width, Height, OffsetX, OffsetY, GainAuto, GainRaw, BlackLevelRaw,
        # BalanceRatio, Pixel_Format
        camera_id = func_input.camera_id
        camera: CameraBasler = self._cameras[camera_id]
        width = func_input.width
        height = func_input.height
        offset_x = func_input.offset_x
        offset_y = func_input.offset_y
        gain_mode = func_input.gain_mode
        if gain_mode not in ['Off', 'Once', 'Continuous']:
            # TODO: finish for other values
            return False, f"GainAuto value must be one of 'Off, Once, Continuous', instead of {gain_mode}."
        gain = func_input.gain
        blacklevel = func_input.blacklevel
        balance_ratio = func_input.balance_ratio
        pixel_format = func_input.pixel_format

        formed_parameters_dict_AOI = {'Width': width, 'Height': height, 'OffsetX': offset_x, 'OffsetY': offset_y}
        formed_parameters_dict_analog_controls = {'GainAuto': gain_mode, 'GainRaw': gain, 'BlackLevelRaw': blacklevel,
                                                  'BalanceRatioRaw': balance_ratio}
        formed_parameters_dict_image_format = {'PixelFormat': pixel_format}

        if self.device_status.active and camera.pylon_camera.IsOpen() and camera.status != 2:
            try:
                for param_name, param_value in {**formed_parameters_dict_AOI, **formed_parameters_dict_analog_controls,
                                                **formed_parameters_dict_image_format}.items():
                    setattr(camera.pylon_camera, param_name, param_value)
                camera.parameters['AOI_Controls'] = AOI_Controls(width, height, offset_x, offset_y)
                camera.parameters['Analog_Controls'] = Analog_Controls(gain_mode, gain, blacklevel, balance_ratio)
                camera.parameters['Image_Format_Control'] = Image_Format_Control(pixel_format)

                return True, ''
            except (genicam.GenericException, Exception) as e:
                return False, f'Error appeared: {e} when setting parameter "{param_name}" for camera with id ' \
                              f'{camera.device_id}.'
        else:
            return False, f'Device_status: {DeviceStatus}, Basler_Camera with id {camera.device_id} connected ' \
                          f'{camera.pylon_camera.IsOpen()}'

    def _set_sync_parameters_device(self, func_input: FuncSetSyncParametersInput) -> Tuple[bool, str]:
        # Essential parameters for Basler are FrameRate, TriggerMode, TriggerSource, ExposureTime
        camera_id = func_input.camera_id
        camera: CameraBasler = self._cameras[camera_id]
        exposure_time = func_input.exposure_time
        trigger_delay = func_input.trigger_delay
        frame_rate = func_input.frame_rate
        trigger_source = func_input.trigger_source
        trigger_mode = 'On' if func_input.trigger_mode else 'Off'

        formed_parameters_dict = {'TriggerSource': trigger_source, 'TriggerMode': trigger_mode,
                                  'TriggerDelayAbs': trigger_delay, 'ExposureTimeAbs': exposure_time,
                                  'AcquisitionFrameRateAbs': frame_rate, 'AcquisitionFrameRateEnable': True}

        if self.device_status.active and camera.pylon_camera.IsOpen() and camera.status != 2:
            try:
                for param_name, param_value in formed_parameters_dict.items():
                    setattr(camera.pylon_camera, param_name, param_value)
                camera.parameters['Acquisition_Controls'] = Acquisition_Controls(trigger_source, trigger_mode,
                                                                                 trigger_delay, exposure_time,
                                                                                 frame_rate)
                return True, ''
            except (genicam.GenericException, Exception) as e:
                return False, f'Error appeared: {e} when setting parameter "{param_name}" for camera with id ' \
                              f'{camera.device_id}.'
        else:
            return False, f'Device_status: {DeviceStatus}, Basler_Camera with id {camera.device_id} connected ' \
                          f'{camera.pylon_camera.IsOpen()}'

    def _set_db_attribute(self, data_class, func):
        obligation_keys = set(data_class.__annotations__.keys())
        attribute_name = data_class.__name__
        try:
            settings = self.get_settings(attribute_name)
            if set(settings.keys()).intersection(obligation_keys) != obligation_keys:
                raise KeyError
            else:
                for camera_key, camera in self._cameras.items():
                    camera.parameters[attribute_name] = data_class()
            for analog_key, analog_value in settings.items():
                if analog_key in obligation_keys:
                    try:
                        analog_value = eval(analog_value)
                    except (SyntaxError, NameError):
                        pass
                    if isinstance(analog_value, dict):
                        dict_opt = True
                    else:
                        dict_opt = False

                    for camera_key, camera in self._cameras.items():
                        try:
                            value = analog_value if not dict_opt else analog_value[camera.device_id]
                            t = data_class.__annotations__[analog_key]
                            if t == bool and isinstance(value, str):
                                value = strtobool(value)
                            value = t(value)
                            setattr(camera.parameters[attribute_name], analog_key, value)
                        except KeyError:
                            raise KeyError(f'Not all cameras ids are passed to {attribute_name} attribute {analog_key}.')
                        except ValueError:
                            raise ValueError(f'Cannot convert {attribute_name} attribute {value} to correct type '
                                             f'{data_class.__annotations__[analog_key]}.')
                else:
                    info_msg(self, 'INFO', f'Unknown parameter {analog_key} in {attribute_name} settings. Passing by.')
        except (KeyError, ValueError) as e:
            error_logger(self, func, e)
            raise CameraError(self, f'Check DB for {attribute_name}: {list(obligation_keys)}. {e}')

    def _release_hardware(self) -> Tuple[bool, str]:
        # TODO: make it work
        try:
            device_id_camera_id = self.device_id_to_id
            for camera_id, pylon_camera in enumerate(self.pylon_cameras):
                device_id = int(pylon_camera.GetDeviceInfo().GetSerialNumber())
                if pylon_camera.IsOpen():
                    pylon_camera.Close()
                    self._cameras[device_id_camera_id[device_id]].status = 0
                self._cameras[device_id_camera_id[device_id]].pylon_camera = None
                return True, ''
        except (genicam.GenericException, Exception) as e:
            error_logger(self, self._release_hardware, e)
            return False, f'Release_hardware function did not work: {e}.'


