# certPortal Playwright Feedback Log

<!-- Append-only. New entries added after each run that has FAILs or RESOLVEDs. -->
<!-- Run  python -m playwrightcli --consolidate  to synthesize into memory.md. -->

## Run 2026-03-13T04:51:28
### FAIL pam::suppliers
  attempted: step fn + corrections: relogin
  error: \Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, 
  correction: Tried: relogin
  note: Failed after 3 retries
### FAIL meredith::supplier-status
  attempted: step fn + corrections: relogin
  error: \Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, 
  correction: Tried: relogin
  note: Failed after 3 retries

## Run 2026-03-13T05:01:45
### FAIL pam::suppliers
  attempted: step fn + corrections: relogin
  error: \Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, 
  correction: Tried: relogin
  note: Failed after 3 retries
### FAIL meredith::supplier-status
  attempted: step fn + corrections: relogin
  error: \Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, 
  correction: Tried: relogin
  note: Failed after 3 retries

## Run 2026-03-14T14:34:58
### FAIL meredith::spec-setup
  attempted: step fn + corrections: relogin
  error: \_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connection.wrap
  correction: Tried: relogin
  note: Failed after 3 retries

## Run 2026-03-14T14:35:20
### FAIL meredith::spec-setup
  attempted: step fn + corrections: relogin
  error: \_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connection.wrap
  correction: Tried: relogin
  note: Failed after 3 retries

## Run 2026-03-14T15:14:07
### FAIL meredith::logout
  attempted: step fn + corrections: wait_500
  error: \Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 233, in wait_for_url
    async with self.expect_navigation(
               ^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_event_context_manag
  correction: Tried: wait_500
  note: Failed after 2 retries

## Run 2026-03-14T16:01:39
### FAIL scope::cert-dashboard
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\scope_flow.py", line 217, in _cert_dashboard
    await self._login("cert_supplier")
  File "C:\Users\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::cert-certification
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\scope_flow.py", line 225, in _cert_certification
    await self._login("cert_supplier")
  File "C:\Us
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-14T16:04:23
### FAIL scope::cert-dashboard
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\scope_flow.py", line 217, in _cert_dashboard
    await self._login("cert_supplier")
  File "C:\Users\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::cert-certification
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\scope_flow.py", line 225, in _cert_certification
    await self._login("cert_supplier")
  File "C:\Us
  correction: Tried: networkidle
  note: Failed after 3 retries
