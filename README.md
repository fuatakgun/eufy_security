Welcome to Alpha release of Eufy Security Integration for Home Assistant. Congratulations on being a brave heart and trying this version. 
 
- [Gratitude](#gratitude)
- [How is this working?](#how-is-this-working)
- [Supported or Known Working devices](#supported-or-known-working-devices)
- [Installation](#installation)
    - [Important: You must set Streaming Quality to LOW and Streaming Codec to LOW in all possible places, otherwise Home Assistant will not be able to handle video generation and/or playing.](#important-you-must-set-streaming-quality-to-low-and-streaming-codec-to-low-in-all-possible-places-otherwise-home-assistant-will-not-be-able-to-handle-video-generation-andor-playing)
  - [1. Installing Eufy Security Add-On](#1-installing-eufy-security-add-on)
  - [2. Install go2rtc Add-on](#2-install-go2rtc-add-on)
  - [3. Installing Eufy Security Integration](#3-installing-eufy-security-integration)
  - [4. Setting up your dashboard for camera](#4-setting-up-your-dashboard-for-camera)
- [Features](#features)
- [Example Automations](#example-automations)
  - [Send notification with thumbnail from home assistant](#send-notification-with-thumbnail-from-home-assistant)
    - [Alternative trigger condition](#alternative-trigger-condition)
  - [Unlock safe with code](#unlock-safe-with-code)
- [Debugging Issues](#debugging-issues)
- [Show Off](#show-off)

# Gratitude

- @bropat for building docker image (https://github.com/bropat/eufy-security-ws) so I can wrap it as Home Assistant Add-on. You can also thank him over here: https://ko-fi.com/bropat
- @cdnninja for educating me on github actions and many other good practices
- Home assistant community (https://community.home-assistant.io/t/eufy-security-integration/318353)

# How is this working?

- @bropat built `eufy-security-ws` using `eufy-security-client` to imitate mobile app and web portal functionalities and wrapped `eufy-security-ws` as `hassio-eufy-security-ws` so we can use it as Home Assistant Add-on.
- Add-on requires email address, password, country code, event duration in seconds and trusted device name.
- Every time add-on is started, it forces all other sessions to log off, so you must create a secondary account and share your home/devices with secondary account including admin rights and you must use secondary account credentials on add-on page. Please login once to Eufy mobile app with this secondary account to be sure that devices are available.
- Country code is very crucial to connect to correct regional servers. If your main account has setup in US and if you are trying to login into your secondary account in DE country, your device data would not be found in EU servers. So please pay attention to put correct country code. (Source: Alpha 2 country code https://en.wikipedia.org/wiki/ISO_3166-1#Officially_assigned_code_elements)
- Event duration in seconds correspond to how long (in seconds) entities in home assistant would stay in active. As an example, when camera notices a person, add-on would receive a push notification from Eufy and home assistant integration will active person detected sensor and person detected sensor will stay on state for `event duration in seconds` long.
- Trusted device name is a required identifier for Eufy systems to record this add-on as mobile client, so you can differentiate the connection from this add-on in multi factor authentication (two factor authentication) page.
- As we already called out earlier, add-on heavily relies on push notifications, so you must enable all kind of push notifications (motion detected, person detected, lock events, alarm events etc) in your mobile app. These notifications are not user based but device based so after enabling all these notifications, your main account will probably bloated with many push notifications. In android, there is a setting to disable specific notifications, please use it.

# Supported or Known Working devices

Please check here: https://github.com/bropat/eufy-security-client#known-working-devices

# Installation

In upcoming steps, you are going to install at least one add-on and two integrations.

In Home Assistant eco-system, if you are using Supervised or HASS OS based setup, you can use `Add-ons` page of Home Assistant to install these. If you are running Core or you don't have `Add-ons` option in your setup, you need to install the docker and run these containers yourself. You will see respective commands in respective steps. If you are interested in composing of your docker container, please check the end section

This integration is not part of Home Assistant Core so you have to install this as a custom integration. There are two ways of doing this, either manually downloading and copying files or using HACS (Home Assistant Community Store). I will be using HACS method here.

If you are intending to use this integration for video streaming purposes and if your camera does not support RTSP (Real Time Streaming Protocol) based streaming (no option of continuous or NAS recording in your camera settings), you also need to install webrtc custom integration which would include go2rtc binary (go2rtc also exists as standalone add-on). This add-on will enable us to convert peer to peer (P2P) bytes into a RTSP stream so you can play it nicely inside Home Assistant (with or without RTC) or with VLC Player.

If you are intending to use this integration for video streaming purposes and if your camera supports RTSP, you will probably enjoy reliable stream because generating RTSP stream is responsibility of hardware and it is very much reliable than P2P based streaming. There is no need to convert incoming P2P bytes into RTSP stream. There are some modified version of Android apk of Eufy Security out there which could enable RTSP stream for unsupported devices but I have not tried it. Moreover, I do not own personally a P2P required device, that is because, many times, I cannot replicate your issues locally and we need to work together to debug these issues.

Lastly, your camera would not start streaming magically by itself, you have to call `turn_on` or `turn_off` services of respective camera entities. So, when you first install everything, you would not have any video until you call these functions. Moreover, P2P streaming might stop randomly because of low level technical issues, you can restart it again with `turn_off` and `turn_on`. You can trigger your automation's on camera states (idle, preparing, streaming).

### Important: You must set Streaming Quality to LOW and Streaming Codec to LOW in all possible places, otherwise Home Assistant will not be able to handle video generation and/or playing. ###

So, let's start.

## 1. Installing Eufy Security Add-On

Please follow the guideline from here: https://github.com/bropat/hassio-eufy-security-ws

## 2. Install go2rtc Add-on

This is a must for P2P streaming and nice to have for RTSP streaming. P2P streaming will use go2rtc to generate stream with a specific RTSP address. RTSP streaming will use this for faster streaming.

There are two ways of doing this, either installing add-on itself or installing Webrtc custom integration. I suggest you to install Webrtc custom integration, which includes go2rtc and respective front-end card for faster streaming. 

Installing go2rtc with or without webrtc can be done following this link: [https://github.com/fuatakgun/WebRTC](https://github.com/AlexxIT/WebRTC) . If you prefer to have a dedicadated go2rtc setup (not bundled with webrtc integration), you need to first install over here: https://github.com/AlexxIT/go2rtc

## 3. Installing Eufy Security Integration

1- If you have not already installed, install `HACS` following this guide: [https://hacs.xyz/docs/use/download/download/](https://hacs.xyz/docs/use/download/download/)

2- When `HACS` is ready, search for `Eufy Security` inside `HACS` Integrations. 

3- Install `Eufy Security` integration through HACS, restart your Home Assistant instance.

4- Navigate to `Settings -> Devices & Services` page of Home Assistant(https://your-instance.duckdns.org/config/integrations). Click on `Add Integration` and search for `Eufy Security` (not `Eufy`, it is `Eufy Security` exactly). If you do not see it, first validate that it is installed via HACS and you had restarted it, later try with another browser. Integrations list might be already cached in your browser.

5- Put `Eufy Security Add-on IP Address` (127.0.0.1 for Supervised installation) and `configured port` (default 3000) and click Submit.

6- You might receive Captcha or Multi Factor Authentications (MFA) warnings, please Reconfigure the integration. Captcha code will be visible on Reconfigure page and MFA Code will be emailed or texted to you. Please enter these values. After this, you might need to restart your Home Assistant instance.

7- If you have installed `webrtc custom integration with go2rtc or standalone go2rtc Add-On`, please put its `IP Address` into Integration Configuration page. You can put `127.0.0.1` for Supervised installation.

8- You can also configure `Cloud Scan Interval`, Video Analyze Duration, `Custom Name 1`, `Custom Name 2` and `Custom Name 3`

Note: Custom Name 1, Custom Name 2, and Custom Name 3 are labels used to represent the first, second, and third custom guards (modes) you've created in the Eufy Security app. You can trigger your custom guards using the built-in alarm panel card like so:

```
arm_custom_bypass -> triggers your first custom guard defined in Eufy security app (ordered by 'created date')
arm_night -> trigger second custom guard
arm_vacation -> trigger third custom guard
```

For example, you create a "bedtime" mode in Eufy Security app, by default there would be no way to trigger that using the alarm panel card. However, using this integration, you can call the `arm_custom_bypass` service from the alarm panel, which will enable your "bedtime" mode. You can adjust the display name of this mode using Step 8 above.

These built-in alarm panel services do not correspond with any default Eufy guards, so they are re-purposed to allow further flexibility to trigger custom security modes using this integration. See discussion in #145 for more details.

![image](https://user-images.githubusercontent.com/11085566/210082270-4de06bbe-0d10-4dde-9fd3-cb12d6758b67.png)

![image](https://user-images.githubusercontent.com/11085566/210082270-4de06bbe-0d10-4dde-9fd3-cb12d6758b67.png)

9- Enable diagnostic entities that are disabled by default. After installation, some entities are disabled to avoid generating too large amounts of data. This is expected behavior. If you think any entity is important, just enable it. To do this select one of the device in eufy_security integrations. Then scroll down to Diagnostic section and select one of entity. In top go to settings and turn on `Enabled` and `Visible` parameters in settings. After around 30 seconds this entity will be available.

## 4. Setting up your dashboard for camera

Native Home Assistant streaming is fairly slow (maybe not?), so you are highly advised to install WebRTC integration from HACS.

Below code will show camera picture while camera is not streaming and webrtc card while camera is streaming (conditional cards). Please replace `camera.entrance` with your camera entity name.

```yaml
type: custom:webrtc-camera
entity: camera.entrance
poster: image.entrance_event_image
ui: true
shortcuts:
  - name: Play
    icon: mdi:play
    service: camera.turn_on
    service_data:
      entity_id: camera.entrance
  - name: Stop
    icon: mdi:stop
    service: camera.turn_off
    service_data:
      entity_id: camera.entrance

```

If your camera supports pan and tilt, you can add respective commands to webrtc interface.

```yaml
type: custom:webrtc-camera
entity: camera.garden
ptz:
  service: eufy_security.ptz
  data_left:
    entity_id: camera.garden
    direction: LEFT
  data_right:
    entity_id: camera.garden
    direction: RIGHT
  data_up:
    entity_id: camera.garden
    direction: UP
  data_down:
    entity_id: camera.garden
    direction: DOWN
```

# Features

- There are many sensors available out there, if you need an additional one, raise a request and share your `Debug (device)` and `Debug (station)` sensor attributes so I can extract these sensors. If these sensors cannot be extracted from state of device, please mention it explicitly.
- There are many `button`, `switch` and `select` entities, please use them.
- Integration Services;
  - Force Sync - Integration will get latest changes from cloud. Some features are not updated via push notifications, you can call this if you want and integration will call this regularly.
- Camera Services;
  - `turn_on` and `turn_off` - Integration will check if your device supports RTSP and fallback P2P based streaming
  - `start_rtsp_livestream` and `stop_rtsp_livestream` - Stream will be started using RTSP if your device supports it
  - `start_p2p_livestream` and `stop_p2p_livestream` - Stream will be started using P2P, all devices work here
  - `generate_image` - This will generate a thumbnail for Home Assistant if camera is already streaming
  - `ptz_up`, `ptz_down`, `ptz_right`, `ptz_left`, `ptz_360` - Pan and Tilt commands
  - `trigger_camera_alarm_with_duration` - Trigger alarm on camera for a given duration
  - `quick_response` - Send a quick response message for doorbell, you can get `voice_id` information from `Debug (device)` sensor attributes of device. This can be executed ONLY when camera is live streaming (p2p - not rtsp)
  - `snooze` - Snooze ongoing notification for a given duration.
- Alarm Panel Services;
  - There is an select entity called Guard Mode, it is one to one mapping of Eufy Security state. Current Mode sensor is showing the current state of home base.
  - `trigger_base_alarm_with_duration` - Trigger alarm on station for a given duration
  - `reset_alarm` - Reset ongoing alarm for a given duration
  - `snooze` - Snooze ongoing notification for a given duration.
  - `arm_home` - Switch to Home state
  - `arm_away` - Switch to Away state
  - `disarm` - Disarm the panel
  - `alarm_arm_custom1` - Switch to custom 1, which relates to the first, second, and third custom guards (or modes) you have created in the Eufy Security app.
  - `alarm_arm_custom2` - Switch to custom 2
  - `alarm_arm_custom3` - Switch to custom 3
  - `geofence` - Switch to geofencing, this might not impact the state of panel given that it will change its state based on geo location via Eufy app
  - `schedule` - Switch to custom 3, this might not impact the state of panel given that it will change its state based on schedule via Eufy app
  - `chime` - Trigger a chime sound on base station (liked it) - I do not know exact list of ringtones available, try it yourself.
- Lock Services;
  - `lock` and `unlock` for locks
  - `unlock` with code for safes

# Example Automations

## Send notification with thumbnail from home assistant

Replace `camera.entrance` with your own entity name.

```yaml
alias: Capture Image on Trigger, Send Mobile Notification with Actions, Snooze or Alarm via Actions
description: ""
trigger:
  - platform: state
    entity_id:
      - binary_sensor.entrance_motion_detected
      - binary_sensor.entrance_person_detected
    to: "on"
    id: sensor
  - platform: event
    event_type: mobile_app_notification_action
    id: snooze
    event_data:
      action: SNOOZE
  - platform: event
    event_type: mobile_app_notification_action
    id: alarm
    event_data:
      action: ALARM
condition: []
action:
  - choose:
      - conditions:
          - condition: trigger
            id: sensor
        sequence:
          - delay:
            hours: 0
            minutes: 0
            seconds: 3
            milliseconds: 0
          - service: notify.mobile_app_fuatx3pro
            data:
              message: Motion detected
              data:
                image: /api/image_proxy/image.entrance_event_image
                actions:
                  - action: ALARM
                    title: Alarm
                  - action: SNOOZE
                    title: Snooze
      - conditions:
          - condition: trigger
            id: snooze
        sequence:
          - service: eufy_security.snooze
            data:
              snooze_time: 10
              snooze_chime: false
              snooze_motion: true
              snooze_homebase: false
            target:
              entity_id: camera.entrance
      - conditions:
          - condition: trigger
            id: alarm
        sequence:
          - service: eufy_security.trigger_camera_alarm_with_duration
            data:
              duration: 1
            target:
              entity_id: camera.entrance
mode: single
```

### Alternative trigger condition

This trigger condition starts the automation right when the event picture updates. In some installations it's more reliable and a bit quicker. If the previous automation gives you outdated images or causes problems, try this different trigger and condition instead:

```yaml
trigger:
  - platform: state
    entity_id:
      - image.entrance_cam
    id: sensor
condition:
  - condition: template
    value_template: >-
      {{ as_timestamp(states.image.entrance_cam.last_changed) == as_timestamp(states.image.entrance_cam.last_updated) }}
```

## Unlock safe with code

```yaml
service: lock.unlock
data:
  code: "testtest"
target:
  entity_id: lock.safe
```

# Debugging Issues

First, check all issues (open or close) to find out if there was any similar question rather than duplicating it.
Focus on enabling push notification settings, lowering camera streaming/recording quality and removing any network level isoloation/restriction. Most of the issues could be eliminated via these.
Later on, if you find a similar issue, please just put +1 on it, sharing same logs over and over does not help at all.
Lastly, create your issue following the template. I will probably ask follow up questions later on.

I am more than happy to debug individual issues as long as you follow setup instructions. I need you to share your problematic cameras with me so that I can use my own machine to debug the issue. For each debugging request, please create a github issue so we can track from there. Do not forget to remove the sharing settings after we are done :)

- If you are located in EU, use my account: fuatakgun@gmail.com
- If you are located in US, use shared test account: eufydeveloper@gmail.com

To schedule the time, please use this link: https://calendly.com/fuatakgun/office-hour

# Show Off

![image](https://user-images.githubusercontent.com/11085566/210081589-43ce2e52-a9e7-4f25-9238-bcdd6212852d.png)
![image](https://user-images.githubusercontent.com/11085566/210081619-6cc1e0d1-ecca-49ee-b18c-d1348db1feee.png)
![image](https://user-images.githubusercontent.com/11085566/210081657-a839623a-1d89-4a15-93d9-1025fd44803d.png)
![image](https://user-images.githubusercontent.com/11085566/210081673-b2a92eaa-9763-4913-a955-c6a48753d5ba.png)
![image](https://user-images.githubusercontent.com/11085566/210081687-148d63d4-9bf8-4d47-81f1-6ed09584141a.png)
![image](https://user-images.githubusercontent.com/11085566/210081954-14e83d45-7bc6-4623-b13b-fb458d0caad5.png)
![image](https://user-images.githubusercontent.com/11085566/210081967-46926dad-55de-4a36-b4ba-a4b6ae99c7ac.png)

https://user-images.githubusercontent.com/11085566/210083674-bbf082ab-5f20-4d1c-ab61-e687c7ce7506.mp4
