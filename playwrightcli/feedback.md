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

## Run 2026-03-15T05:34:30
### FAIL template::tpl-05-save-draft
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-06-publish-template
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\template_flow.py", line 119, in _publish_template
    assert "published" in body or "template" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T05:41:04
### FAIL exception::exc-06-confirm-pending-status
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 144, in _confirm_pending
    assert "pending" in body or "exception" in body
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T05:52:03
### FAIL onboarding::onb-05-step1-gate-a-set
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 125, in _step1_verify_gate_a
    assert "company" in body or "contact" in b
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: s\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\pla
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: grams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line
  correction: Tried: networkidle
  note: Failed after 3 retries
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
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 186, in _step4_check_table
    assert "vendor" in body or "part number" in 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 208, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 213, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 217, in _step5_exception
    assert "exception" in body, "Exception request
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 227, in _step6_check
    assert "onboarding" in body or "step" in body or "
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T06:00:39
### FAIL exception::exc-06-confirm-pending-status
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 146, in _confirm_pending
    assert "pending" in body or "exception" in body
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-11-verify-approved-status
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 180, in _verify_approved
    assert "approved" in body, "APPROVED status not
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T06:02:06
### FAIL template::tpl-05-save-draft
  attempted: step fn + corrections: networkidle
  error: pl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_c
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-06-publish-template
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\template_flow.py", line 126, in _publish_template
    assert "published" in body or "template" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T06:05:06
### FAIL onboarding::onb-05-step1-gate-a-set
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 125, in _step1_verify_gate_a
    assert "company" in body or "contact" in b
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: s\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\pla
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: grams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line
  correction: Tried: networkidle
  note: Failed after 3 retries
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
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 186, in _step4_check_table
    assert "vendor" in body or "part number" in 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 208, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 213, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 217, in _step5_exception
    assert "exception" in body, "Exception request
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 227, in _step6_check
    assert "onboarding" in body or "step" in body or "
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T06:16:59
### FAIL onboarding::onb-05-step1-gate-a-set
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 125, in _step1_verify_gate_a
    assert "company" in body or "contact" in b
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: s\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\pla
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: grams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line
  correction: Tried: networkidle
  note: Failed after 3 retries
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
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 186, in _step4_check_table
    assert "vendor" in body or "part number" in 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 208, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 213, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 217, in _step5_exception
    assert "exception" in body, "Exception request
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 227, in _step6_check
    assert "onboarding" in body or "step" in body or "
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T06:46:37
### FAIL onboarding::onb-05-step1-gate-a-set
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 125, in _step1_verify_gate_a
    assert "company" in body or "contact" in b
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: s\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\pla
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: grams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line
  correction: Tried: networkidle
  note: Failed after 3 retries
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
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 186, in _step4_check_table
    assert "vendor" in body or "part number" in 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 208, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 213, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 217, in _step5_exception
    assert "exception" in body, "Exception request
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 227, in _step6_check
    assert "onboarding" in body or "step" in body or "
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T07:08:09
### FAIL onboarding::onb-05-step1-gate-a-set
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 125, in _step1_verify_gate_a
    assert "company" in body or "contact" in b
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: s\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\pla
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: grams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line
  correction: Tried: networkidle
  note: Failed after 3 retries
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
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 186, in _step4_check_table
    assert "vendor" in body or "part number" in 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: ams\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 60, in __aexit__
    await self._event.value
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_async_base.py", line 35, in value
    return mapping.from_maybe_impl(await
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 208, in _step5_scenarios
    assert "scenario" in body or "850" in body or 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 213, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 217, in _step5_exception
    assert "exception" in body, "Exception request
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 227, in _step6_check
    assert "onboarding" in body or "step" in body or "
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T07:27:53
### FAIL exception::exc-07-retailer-login
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-08-navigate-exception-queue
  attempted: step fn + corrections: networkidle
  error: 2\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connectio
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-09-verify-request-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 168, in _verify_request_visible
    assert "exception" in body and ("approve
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-10-approve-exception
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 178, in _approve_exception
    raise AssertionError("No Approve button found
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-11-verify-approved-status
  attempted: step fn + corrections: networkidle
  error: 2\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connectio
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T07:32:35
### FAIL template::tpl-01-admin-login
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-02-navigate-templates-new
  attempted: step fn + corrections: networkidle
  error: on312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._conne
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-03-fill-template-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-04-fill-template-body
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-05-save-draft
  attempted: step fn + corrections: networkidle
  error: on312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._conne
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-06-publish-template
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\template_flow.py", line 131, in _publish_template
    assert "published" in body or "template" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-07-retailer-login
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-08-verify-template-visible
  attempted: step fn + corrections: networkidle
  error: Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connection.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-09-adopt-template
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\template_flow.py", line 157, in _adopt_template
    assert "adopt" in body or "template" in body, "Ad
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-10-fork-template
  attempted: step fn + corrections: networkidle
  error: Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connection.
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T07:37:02
### FAIL visual::vis-01-pam-dashboard-screenshot
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 68, in _vis_01
    raise AssertionError(f"certportal-core.css not lo
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-02-meredith-wizard-screenshot
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 85, in _vis_02
    raise AssertionError(f"portal-{portal}.css not lo
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-03-chrissy-onboarding-screenshot
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 112, in _vis_03
    raise AssertionError("Dark mode toggle button (#
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-04-responsive-mobile-viewport
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 132, in _vis_04
    raise AssertionError(f"nav.nav not found on {url
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T07:38:14
### FAIL visual::vis-01-pam-dashboard-screenshot
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 68, in _vis_01
    raise AssertionError(f"certportal-core.css not lo
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-02-meredith-wizard-screenshot
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 85, in _vis_02
    raise AssertionError(f"portal-{portal}.css not lo
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-03-chrissy-onboarding-screenshot
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 112, in _vis_03
    raise AssertionError("Dark mode toggle button (#
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-04-responsive-mobile-viewport
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 132, in _vis_04
    raise AssertionError(f"nav.nav not found on {url
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T07:39:26
### FAIL visual::vis-05-dark-mode-toggle
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\visual_regression_flow.py", line 148, in _vis_05
    raise AssertionError(f"Horizontal scroll detecte
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T08:21:34
### FAIL onboarding::onb-03-step1-spec-download-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 108, in _step1_spec_visible
    assert "specification" in body or "download
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-04-step1-acknowledge
  attempted: step fn + corrections: networkidle
  error: :\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 488, in click
    await self._channel.send("click", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connect
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: n312\Lib\site-packages\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-12-step3-fill-test-ids
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-13-step3-gate-1-set
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 488, in click
    await self._channel.send("click", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python3
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-14-step4-add-item-row
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-15-step4-fill-item-data
  attempted: step fn + corrections: networkidle
  error: thon\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 128, in _query_count
    return await self._channel.send("queryCount", {"selector": selector})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python3
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: ion, arg)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 278, in evaluate
    await self._channel.send(
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python3
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: \Lib\site-packages\playwright\_impl\_frame.py", line 613, in text_content
    return await self._channel.send("textContent", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\L
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: \Lib\site-packages\playwright\_impl\_frame.py", line 613, in text_content
    return await self._channel.send("textContent", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\L
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-12-verify-kelly-signal
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 192, in _verify_kelly_signal
    found = self._verifier.signal_checker.find_
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T13:54:59
### FAIL onboarding::onb-03-step1-spec-download-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 108, in _step1_spec_visible
    assert "specification" in body or "download
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-04-step1-acknowledge
  attempted: step fn + corrections: networkidle
  error: :\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 488, in click
    await self._channel.send("click", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connect
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: n312\Lib\site-packages\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-12-step3-fill-test-ids
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-13-step3-gate-1-set
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 488, in click
    await self._channel.send("click", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python3
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-14-step4-add-item-row
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-15-step4-fill-item-data
  attempted: step fn + corrections: networkidle
  error: thon\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 128, in _query_count
    return await self._channel.send("queryCount", {"selector": selector})
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python3
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: ion, arg)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 278, in evaluate
    await self._channel.send(
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python3
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: \Lib\site-packages\playwright\_impl\_frame.py", line 613, in text_content
    return await self._channel.send("textContent", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\L
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: \Lib\site-packages\playwright\_impl\_frame.py", line 613, in text_content
    return await self._channel.send("textContent", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\L
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Pyt
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-12-verify-kelly-signal
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 192, in _verify_kelly_signal
    found = self._verifier.signal_checker.find_
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T14:21:18
### FAIL onboarding::onb-03-step1-spec-download-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 108, in _step1_spec_visible
    assert "specification" in body or "download
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-04-step1-acknowledge
  attempted: step fn + corrections: networkidle
  error: :\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 488, in click
    await self._channel.send("click", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connect
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-06-step2-fill-contact-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-07-step2-fill-contact-email
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packa
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-08-step2-fill-contact-phone
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-09-step2-fill-contact-role
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packag
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-10-step2-gate-b-set
  attempted: step fn + corrections: networkidle
  error: s\playwright\_impl\_frame.py", line 687, in input_value
    return await self._channel.send("inputValue", locals_to_params(locals()))
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\pla
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: grams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line
  correction: Tried: networkidle
  note: Failed after 3 retries
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
  error: al\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 488, in click
    await self._channel.send("click", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
   
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-14-step4-add-item-row
  attempted: step fn + corrections: networkidle
  error: n\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-16-step4-items-complete
  attempted: step fn + corrections: networkidle
  error: C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 488, in click
    await self._channel.send("click", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connec
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-17-step5-scenario-list-visible
  attempted: step fn + corrections: networkidle
  error: n\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-18-step5-required-badges
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 213, in _step5_badges
    assert "required" in body, "REQUIRED badges not f
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-19-step5-exception-request-button
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\onboarding_flow.py", line 217, in _step5_exception
    assert "exception" in body, "Exception request
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-20-step6-production-ids-gate3-pending
  attempted: step fn + corrections: networkidle
  error: n\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-01-supplier-login
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-02-navigate-exceptions
  attempted: step fn + corrections: networkidle
  error: n\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-03-select-reason-code
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 109, in _verify_reason_dropdown
    assert "exception" in body or "request" 
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-04-fill-justification
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 115, in _verify_note_field
    assert "exception" in body or "scenario" in b
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-06-confirm-pending-status
  attempted: step fn + corrections: networkidle
  error: Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
  
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-07-retailer-login
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-08-navigate-exception-queue
  attempted: step fn + corrections: networkidle
  error: 2\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connectio
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-09-verify-request-visible
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 168, in _verify_request_visible
    assert "exception" in body and ("approve
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-10-approve-exception
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 178, in _approve_exception
    raise AssertionError("No Approve button found
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-11-verify-approved-status
  attempted: step fn + corrections: networkidle
  error: 2\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connectio
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-12-verify-kelly-signal
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 192, in _verify_kelly_signal
    found = self._verifier.signal_checker.find_
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-01-admin-login
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-02-navigate-templates-new
  attempted: step fn + corrections: networkidle
  error: on312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._conne
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-03-fill-template-name
  attempted: step fn + corrections: networkidle
  error: ^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-04-fill-template-body
  attempted: step fn + corrections: networkidle
  error: ^^^^^^^
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-05-save-draft
  attempted: step fn + corrections: networkidle
  error: on312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._conne
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-06-publish-template
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\template_flow.py", line 131, in _publish_template
    assert "published" in body or "template" in bod
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-07-retailer-login
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-08-verify-template-visible
  attempted: step fn + corrections: networkidle
  error: Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connection.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-09-adopt-template
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\template_flow.py", line 157, in _adopt_template
    assert "adopt" in body or "template" in body, "Ad
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL template::tpl-10-fork-template
  attempted: step fn + corrections: networkidle
  error: Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connection.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-01-login-chrissy
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-02-navigate-onboarding
  attempted: step fn + corrections: networkidle
  error: n\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self.
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-03-step2-locked-before-gate-a
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\gate_model_flow.py", line 87, in _step2_locked
    assert count > 0, "No locked steps found — gate se
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-04-gate-a-binary-value
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\gate_model_flow.py", line 96, in _gate_a_binary
    assert count >= 5, f"Expected 5 gate pills (A,B,1
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-05-step3-locked-before-gate-b
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\gate_model_flow.py", line 105, in _step3_locked
    assert active_count >= 1, "No active step indicat
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-06-gate-b-binary-value
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\gate_model_flow.py", line 120, in _gate_b_binary
    assert (total + certified_count) >= 5, \
       
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-07-progress-bar-visible
  attempted: step fn + corrections: networkidle
  error: \AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_co
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL gate_model::gate-08-progress-bar-reflects-status
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\gate_model_flow.py", line 135, in _progress_reflects
    assert total == 6, f"Expected 6 step indicat
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-01-pam-dashboard-screenshot
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-02-meredith-wizard-screenshot
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-03-chrissy-onboarding-screenshot
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-04-responsive-mobile-viewport
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL visual::vis-05-dark-mode-toggle
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-01-pam-login-loads-core
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-02-pam-login-no-inline
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-03-meredith-login-loads-core
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-04-meredith-login-no-inline
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-05-chrissy-login-loads-core
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-06-chrissy-login-no-inline
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-07-pam-forgot-no-inline
  attempted: step fn + corrections: networkidle
  error: 2\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return await self._connectio
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-08-design-tokens-active
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL css-depr::css-depr-09-pam-dark-mode
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T14:30:22
### FAIL onboarding::onb-11-step3-select-connection-method
  attempted: step fn + corrections: networkidle
  error: grams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 323, in wait_for_selector
    await self._channel.send("waitForSelector", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL onboarding::onb-12-step3-fill-test-ids
  attempted: step fn + corrections: networkidle
  error: 
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 527, in fill
    await self._channel.send("fill", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL exception::exc-12-verify-kelly-signal
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 194, in _verify_kelly_signal
    raise AssertionError("exception_resolved si
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T14:34:38
### FAIL exception::exc-12-verify-kelly-signal
  attempted: step fn + corrections: networkidle
  error: Traceback (most recent call last):
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\runner.py", line 95, in run_step
    await fn()
  File "C:\Users\SeanHoppe\vs\certPortal\playwrightcli\flows\exception_flow.py", line 194, in _verify_kelly_signal
    raise AssertionError("exception_resolved si
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T15:08:14
### FAIL scope::supplier-a-scenarios
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::supplier-b-patches
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::supplier-b-scenarios
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::retailer-a-status
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::retailer-b-status
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::cert-dashboard
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries
### FAIL scope::cert-certification
  attempted: step fn + corrections: networkidle
  error: rams\Python\Python312\Lib\site-packages\playwright\_impl\_frame.py", line 145, in goto
    await self._channel.send("goto", locals_to_params(locals()))
  File "C:\Users\SeanHoppe\AppData\Local\Programs\Python\Python312\Lib\site-packages\playwright\_impl\_connection.py", line 59, in send
    return a
  correction: Tried: networkidle
  note: Failed after 3 retries

## Run 2026-03-15T15:14:59
### RESOLVED pam::jwt-revocation
  correction: networkidle
  note: Failed on attempt 1; resolved after correction=networkidle

## Run 2026-03-15T15:15:17
### RESOLVED meredith::login
  correction: networkidle
  note: Failed on attempt 1; resolved after correction=networkidle
