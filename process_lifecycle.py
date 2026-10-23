"""Own only the launched process tree. Windows Job Object prevents orphan children."""
import os
import signal
import subprocess


class ProcessTree:
    def __init__(self):
        self.handle = None
        self.process = None

    def launch(self, command, **kwargs):
        if os.name != "nt":
            self.process = subprocess.Popen(command, start_new_session=True, **kwargs)
            return self.process
        import ctypes as c
        from ctypes import wintypes as w

        class Basic(c.Structure):
            _fields_ = [("process_time", c.c_longlong), ("job_time", c.c_longlong),
                        ("flags", w.DWORD), ("min_ws", c.c_size_t), ("max_ws", c.c_size_t),
                        ("active", w.DWORD), ("affinity", c.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]

        class IO(c.Structure):
            _fields_ = [(name, c.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read", "write", "other")]

        class Extended(c.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", c.c_size_t),
                        ("job_memory", c.c_size_t), ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]

        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [c.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise c.WinError(c.get_last_error())
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, c.byref(info), c.sizeof(info)):
            self.close()
            raise c.WinError(c.get_last_error())
        try:
            # Assign while suspended: no child can escape before ownership is established.
            self.process = subprocess.Popen(command, creationflags=subprocess.CREATE_NO_WINDOW | 4, **kwargs)
            if not self.kernel.AssignProcessToJobObject(self.handle, int(self.process._handle)):
                raise c.WinError(c.get_last_error())
            resume = c.WinDLL("ntdll").NtResumeProcess
            resume.argtypes = [w.HANDLE]
            resume.restype = c.c_long
            if resume(int(self.process._handle)) != 0:
                raise OSError("Impossibile riprendere il processo isolato")
            return self.process
        except Exception:
            if self.process:
                self.process.kill()
                self.process.wait()
                if self.process.stdout:
                    self.process.stdout.close()
            self.close()
            raise

    def terminate(self):
        if self.handle:
            if not self.kernel.TerminateJobObject(self.handle, 1):
                raise OSError("Interruzione del processo non riuscita")
        elif self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
