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

## Run 2026-03-15T04:51:38
### FAIL onboarding::onb-12-step3-fill-test-ids
  attempted: step fn + corrections: networkidle
  error: 
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-13-step3-gate-1-set
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-14-step4-add-item-row
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 172, in _step4_check_table
    assert "vendor" in body or "item" in body or
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 190, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 194, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 198, in _step5_exception_btn
    assert "exception" in body, "Exception req
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 205, in _step6_prod_ids
    assert "production" in body or "go-live" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T04:58:49
### FAIL onboarding::onb-12-step3-fill-test-ids
  attempted: step fn + corrections: networkidle
  error: 
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-13-step3-gate-1-set
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-14-step4-add-item-row
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 174, in _step4_check_table
    assert "vendor" in body or "item" in body or
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 193, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 197, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 201, in _step5_exception_btn
    assert "exception" in body, "Exception req
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 208, in _step6_prod_ids
    assert "production" in body or "go-live" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T05:04:38
### FAIL onboarding::onb-12-step3-fill-test-ids
  attempted: step fn + corrections: networkidle
  error: 
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-13-step3-gate-1-set
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-14-step4-add-item-row
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 174, in _step4_check_table
    assert "vendor" in body or "item" in body or
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 193, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 197, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 201, in _step5_exception_btn
    assert "exception" in body, "Exception req
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 208, in _step6_prod_ids
    assert "production" in body or "go-live" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T05:11:46
### FAIL onboarding::onb-12-step3-fill-test-ids
  attempted: step fn + corrections: networkidle
  error: 
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-13-step3-gate-1-set
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-14-step4-add-item-row
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 179, in _step4_check_table
    assert "vendor" in body or "item" in body or
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 198, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 202, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 206, in _step5_exception_btn
    assert "exception" in body, "Exception req
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 213, in _step6_prod_ids
    assert "production" in body or "go-live" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries
