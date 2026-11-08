using System;
using System.Runtime.InteropServices;
using System.Text;

namespace ximc
{
	public enum Result { ok = 0, error = -1, not_implemented = -2, value_error = -3, no_device = -4 };

	[StructLayout(LayoutKind.Sequential)]
	public struct calibration_t
	{
		public double A;
		public uint MicrostepMode;
	};
	

	public static class Version
	{
		public const String version = "2.10.5";
	};

// Compile this source with ximcnet.structures.cs.
/*
 --------------------------------------------
   BEGIN OF GENERATED function declarations
 --------------------------------------------
*/

	public partial class API
	{
		[DllImport("libximc.dll")]
		public static extern Result set_feedback_settings (int id, ref feedback_settings_t feedback_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_feedback_settings (int id, out feedback_settings_t feedback_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_home_settings (int id, ref home_settings_t home_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_home_settings_calb (int id, ref home_settings_calb_t home_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result get_home_settings (int id, out home_settings_t home_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_home_settings_calb (int id, out home_settings_calb_t home_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_move_settings (int id, ref move_settings_t move_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_move_settings_calb (int id, ref move_settings_calb_t move_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result get_move_settings (int id, out move_settings_t move_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_move_settings_calb (int id, out move_settings_calb_t move_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_engine_settings (int id, ref engine_settings_t engine_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_engine_settings_calb (int id, ref engine_settings_calb_t engine_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result get_engine_settings (int id, out engine_settings_t engine_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_engine_settings_calb (int id, out engine_settings_calb_t engine_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_entype_settings (int id, ref entype_settings_t entype_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_entype_settings (int id, out entype_settings_t entype_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_power_settings (int id, ref power_settings_t power_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_power_settings (int id, out power_settings_t power_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_secure_settings (int id, ref secure_settings_t secure_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_secure_settings (int id, out secure_settings_t secure_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_edges_settings (int id, ref edges_settings_t edges_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_edges_settings_calb (int id, ref edges_settings_calb_t edges_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result get_edges_settings (int id, out edges_settings_t edges_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_edges_settings_calb (int id, out edges_settings_calb_t edges_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_pid_settings (int id, ref pid_settings_t pid_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_pid_settings (int id, out pid_settings_t pid_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_sync_in_settings (int id, ref sync_in_settings_t sync_in_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_sync_in_settings_calb (int id, ref sync_in_settings_calb_t sync_in_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result get_sync_in_settings (int id, out sync_in_settings_t sync_in_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_sync_in_settings_calb (int id, out sync_in_settings_calb_t sync_in_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_sync_out_settings (int id, ref sync_out_settings_t sync_out_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_sync_out_settings_calb (int id, ref sync_out_settings_calb_t sync_out_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result get_sync_out_settings (int id, out sync_out_settings_t sync_out_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_sync_out_settings_calb (int id, out sync_out_settings_calb_t sync_out_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_extio_settings (int id, ref extio_settings_t extio_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_extio_settings (int id, out extio_settings_t extio_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_brake_settings (int id, ref brake_settings_t brake_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_brake_settings (int id, out brake_settings_t brake_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_control_settings (int id, ref control_settings_t control_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_control_settings_calb (int id, ref control_settings_calb_t control_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result get_control_settings (int id, out control_settings_t control_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_control_settings_calb (int id, out control_settings_calb_t control_settings_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_joystick_settings (int id, ref joystick_settings_t joystick_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_joystick_settings (int id, out joystick_settings_t joystick_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_ctp_settings (int id, ref ctp_settings_t ctp_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_ctp_settings (int id, out ctp_settings_t ctp_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_uart_settings (int id, ref uart_settings_t uart_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_uart_settings (int id, out uart_settings_t uart_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_calibration_settings (int id, ref calibration_settings_t calibration_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_calibration_settings (int id, out calibration_settings_t calibration_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_controller_name (int id, ref controller_name_t controller_name);

		[DllImport("libximc.dll")]
		public static extern Result get_controller_name (int id, out controller_name_t controller_name);

		[DllImport("libximc.dll")]
		public static extern Result set_nonvolatile_memory (int id, ref nonvolatile_memory_t nonvolatile_memory);

		[DllImport("libximc.dll")]
		public static extern Result get_nonvolatile_memory (int id, out nonvolatile_memory_t nonvolatile_memory);

		[DllImport("libximc.dll")]
		public static extern Result command_stop (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_add_sync_in_action (int id, ref command_add_sync_in_action_t the_command_add_sync_in_action);

		[DllImport("libximc.dll")]
		public static extern Result command_add_sync_in_action_calb (int id, ref command_add_sync_in_action_calb_t the_command_add_sync_in_action_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result command_power_off (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_move (int id, int Position, int uPosition);

		[DllImport("libximc.dll")]
		public static extern Result command_move_calb (int id, float Position, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result command_movr (int id, int DeltaPosition, int uDeltaPosition);

		[DllImport("libximc.dll")]
		public static extern Result command_movr_calb (int id, float DeltaPosition, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result command_home (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_left (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_right (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_loft (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_sstp (int id);

		[DllImport("libximc.dll")]
		public static extern Result get_position (int id, out get_position_t the_get_position);

		[DllImport("libximc.dll")]
		public static extern Result get_position_calb (int id, out get_position_calb_t the_get_position_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result set_position (int id, ref set_position_t the_set_position);

		[DllImport("libximc.dll")]
		public static extern Result set_position_calb (int id, ref set_position_calb_t the_set_position_calb, ref calibration_t calibration);

		[DllImport("libximc.dll")]
		public static extern Result command_zero (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_save_settings (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_read_settings (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_save_robust_settings (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_read_robust_settings (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_eesave_settings (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_eeread_settings (int id);

		[DllImport("libximc.dll")]
		public static extern Result command_start_measurements (int id);

		[DllImport("libximc.dll")]
		public static extern Result get_measurements (int id, out measurements_t measurements);

		[DllImport("libximc.dll")]
		public static extern Result get_chart_data (int id, out chart_data_t chart_data);

		[DllImport("libximc.dll")]
		public static extern Result get_serial_number (int id, out uint SerialNumber);

		[DllImport("libximc.dll")]
		public static extern Result get_firmware_version (int id, out uint Major, out uint Minor, out uint Release);

		[DllImport("libximc.dll")]
		public static extern Result service_command_updf (int id);

		[DllImport("libximc.dll")]
		public static extern Result set_serial_number (int id, ref serial_number_t serial_number);

		[DllImport("libximc.dll")]
		public static extern Result get_analog_data (int id, out analog_data_t analog_data);

		[DllImport("libximc.dll")]
		public static extern Result get_debug_read (int id, out debug_read_t debug_read);

		[DllImport("libximc.dll")]
		public static extern Result set_debug_write (int id, ref debug_write_t debug_write);

		[DllImport("libximc.dll")]
		public static extern Result set_stage_name (int id, ref stage_name_t stage_name);

		[DllImport("libximc.dll")]
		public static extern Result get_stage_name (int id, out stage_name_t stage_name);

		[DllImport("libximc.dll")]
		public static extern Result set_stage_information (int id, ref stage_information_t stage_information);

		[DllImport("libximc.dll")]
		public static extern Result get_stage_information (int id, out stage_information_t stage_information);

		[DllImport("libximc.dll")]
		public static extern Result set_stage_settings (int id, ref stage_settings_t stage_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_stage_settings (int id, out stage_settings_t stage_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_motor_information (int id, ref motor_information_t motor_information);

		[DllImport("libximc.dll")]
		public static extern Result get_motor_information (int id, out motor_information_t motor_information);

		[DllImport("libximc.dll")]
		public static extern Result set_motor_settings (int id, ref motor_settings_t motor_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_motor_settings (int id, out motor_settings_t motor_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_encoder_information (int id, ref encoder_information_t encoder_information);

		[DllImport("libximc.dll")]
		public static extern Result get_encoder_information (int id, out encoder_information_t encoder_information);

		[DllImport("libximc.dll")]
		public static extern Result set_encoder_settings (int id, ref encoder_settings_t encoder_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_encoder_settings (int id, out encoder_settings_t encoder_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_hallsensor_information (int id, ref hallsensor_information_t hallsensor_information);

		[DllImport("libximc.dll")]
		public static extern Result get_hallsensor_information (int id, out hallsensor_information_t hallsensor_information);

		[DllImport("libximc.dll")]
		public static extern Result set_hallsensor_settings (int id, ref hallsensor_settings_t hallsensor_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_hallsensor_settings (int id, out hallsensor_settings_t hallsensor_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_gear_information (int id, ref gear_information_t gear_information);

		[DllImport("libximc.dll")]
		public static extern Result get_gear_information (int id, out gear_information_t gear_information);

		[DllImport("libximc.dll")]
		public static extern Result set_gear_settings (int id, ref gear_settings_t gear_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_gear_settings (int id, out gear_settings_t gear_settings);

		[DllImport("libximc.dll")]
		public static extern Result set_accessories_settings (int id, ref accessories_settings_t accessories_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_accessories_settings (int id, out accessories_settings_t accessories_settings);

		[DllImport("libximc.dll")]
		public static extern Result get_bootloader_version (int id, out uint Major, out uint Minor, out uint Release);

		[DllImport("libximc.dll")]
		public static extern Result get_init_random (int id, out init_random_t init_random);

		[DllImport("libximc.dll")]
		public static extern Result get_globally_unique_identifier (int id, out globally_unique_identifier_t globally_unique_identifier);

		[DllImport("libximc.dll")]
		public static extern Result command_change_motor (int id, ref command_change_motor_t the_command_change_motor);
	};

/*
 -------------------------
   END OF GENERATED CODE
 -------------------------
*/


	public partial class API
	{   
		private class Impl
		{
			[DllImport("libximc.dll")]
			public static extern IntPtr get_device_name(IntPtr device_enumeration, int device_index);
		};

		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern int open_device ([MarshalAs(UnmanagedType.LPStr)] String name);
		[DllImport("libximc.dll")]
		public static extern Result close_device (ref int id);
		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern Result probe_device ([MarshalAs(UnmanagedType.LPStr)] String name);
		
		[DllImport("libximc.dll")]
		public static extern Result reset_locks ();
		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern Result ximc_fix_usbser_sys ([MarshalAs(UnmanagedType.LPStr)] String name);
		[DllImport("libximc.dll")]
		public static extern Result get_device_information (int id, out device_information_t device_information);
		[DllImport("libximc.dll")]
		public static extern Result get_status (int id, out status_t status);
		[DllImport("libximc.dll")]
		public static extern Result get_status_calb (int id, out status_calb_t status, ref calibration_t calibration);
		[DllImport("libximc.dll")]
		public static extern Result goto_firmware(int id, out byte ret);
		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern Result has_firmware([MarshalAs(UnmanagedType.LPStr)] String name, out byte ret);
		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern Result write_key([MarshalAs(UnmanagedType.LPStr)] String name, byte[] key);
		[DllImport("libximc.dll")]
		public static extern Result command_reset(int id);
		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern Result command_update_firmware([MarshalAs(UnmanagedType.LPStr)] String name, byte[] data, uint data_size);
		[DllImport("libximc.dll")]
		public static extern void msec_sleep(int id);
		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern void ximc_version(StringBuilder version);
		
		[DllImport("libximc.dll", CharSet = CharSet.Ansi)]
		public static extern IntPtr enumerate_devices(int enumerate_flags, [MarshalAs(UnmanagedType.LPStr)] String hints);
		[DllImport("libximc.dll")]
		public static extern Result enumerate_devices(IntPtr device_enumeration);
		[DllImport("libximc.dll")]
		public static extern Result free_enumerate_devices(IntPtr device_enumeration);
		[DllImport("libximc.dll")]
		public static extern int get_device_count(IntPtr device_enumeration);

		public static String get_device_name(IntPtr device_enumeration, int device_index)
		{
			return System.Runtime.InteropServices.Marshal.PtrToStringAnsi(
					Impl.get_device_name(device_enumeration, device_index));
		}


		[DllImport("libximc.dll")]
		public static extern Result get_enumerate_device_information(IntPtr device_enumeration, int device_index, 
				out device_information_t device_information);
		[DllImport("libximc.dll")]
		public static extern Result get_enumerate_device_serial(IntPtr device_enumeration, int device_index,
				out UInt32 serial);

		public enum LogLevel { error = 0x01, warning = 0x02, info = 0x03, debug = 0x04 };

		[UnmanagedFunctionPointer(CallingConvention.StdCall)]
		public delegate void LoggingCallback ([MarshalAs(UnmanagedType.I4)] LogLevel loglevel,
				[MarshalAs(UnmanagedType.LPWStr)] string message, IntPtr user_data);
		
		[DllImport("libximc.dll")]
		public static extern void set_logging_callback([MarshalAs(UnmanagedType.FunctionPtr)] LoggingCallback logging_callback, IntPtr user_data);
	
		[DllImport("libximc.dll")]
		public static extern Result command_wait_for_stop(int id, int wait_interval_ms);

		[DllImport("libximc.dll")]
		public static extern Result set_bindy_key([MarshalAs(UnmanagedType.LPStr)] String keyfilepath);
	};

};

