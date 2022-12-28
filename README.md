Welcome to Alpha release of Eufy Security Integration for Home Assistant. Congragulations on being a brave heart and trying this version.

# Gratitude #
- @bropat for building docker image (https://github.com/bropat/eufy-security-ws) so I can wrap it as Home Assistant Add-on. You can also thank him over here: https://ko-fi.com/bropat
- @cdnninja for educating me on github actions and many other good practices
- Home assistant community (https://community.home-assistant.io/t/eufy-security-integration/318353)

# How is this working ? #
- @bropat built `eufy-security-ws` using `eufy-security-client` to imitate mobile app and web portal functionalities and I had wrapped `eufy-security-ws` as `eufy_security_addon` so we can use it as Home Assistant Add-on.
- Add-on requires email address, password, country code, event duration in seconds and trusted device name.
- Every time add-on is started, it forces all other sessions to log off, so you must create a secondary account and share your home/devices with secondary account including admin rights and you must use secondary account credentials on add-on page. Please login once to eufy mobile app with this secondary account to be sure that devices are available.
- Country code is very crucial to connect to correct regional servers. If your main account has setup in US and if you are trying to login into your secondary account in DE country, your device data would not be found in EU servers. So please pay attention to put correct country code. (Source: Alpha 2 country code https://en.wikipedia.org/wiki/ISO_3166-1#Officially_assigned_code_elements)
- Event duration in seconds correspond to how long (in seconds) entities in home assistant would stay in active. As an example, when camera notices a person, add-on would receive a push notification from eufy and home assistant integration will active person detected sensor and person detected sensor will stay on state for `event duration in seconds` long.
- Trusted device name is a required identifier for eufy systems to record this add-on as mobile client, so you can differentiate the connection from this add-on in multi factor authentication (two factor authentication) page.
- **As we already called out earlier, add-on heavily relies on push notifications, so you must enable all kind of push notifications in your mobile app. These notifications are not user based but device based so after enabling all these notifications, your main account will probably bloated with many push notifications. In android, there is a setting to disable specific notifications, please use it.**

# Supported or Known Working devices #
Please check here: https://github.com/bropat/eufy-security-client#known-working-devices

# Installation #
In upcoming steps, you are going to install at least one add-on and one integration.

In Home Assistant eco-system, if you are using Supervised or HASS OS based setup, you can use `Add-ons` page of Home Assistant to install these. If you are running Core or you don't have `Add-ons` option in your setup, you need to install the docker and run these containers yourself. You will see respective commands in respective steps.

This integration is not part of Home Assistant Core so you have to install this as a custom integration. There are two ways of doing this, either manaully downloading and copying files or using HACS (Home Assistant Community Store). I will be using HACS method here.

If you are intending to use this integration for video streaming purposes and if your camera does not support RTSP (Real Time Streaming Protocol) based streaming (no optino of continous or NAS recording in your camera settings), you also need to install RTSP Simple Server Add-on. This add-on will enable us to convert peer to peer (P2P) bytes into a RTSP stream so you can play it nicely inside Home Assistant (with or without RTC) or with VLC Player.

If you are intending to use this integration for video streaming purposes and if your camera supports RTSP, you will probabaly enjoy reliable stream because generating RTSP stream is responsibility of hardware and it is very much reliable than P2P based streaming. There is no need to convert incoming P2P bytes into RTSP stream. There are some modified version of Android apk of Eufy Security out there which could enable RTSP stream for unsupported devices but I have not tried it. Moreover, I do not own personally a P2P required device, that is because, many times, I cannot replicate your issues locally and we need to work together to debug these issues.

So, let's start.

## 1. Installing Eufy Security Add-On ##
1- Add 'Eufy Security Add-On Repository' to Add-On Store. Please follow steps located here (https://www.home-assistant.io/common-tasks/os#installing-third-party-add-ons) and use this repository URL (https://github.com/fuatakgun/eufy_security_addon)

2- Search 'Eufy Security' on Add-on Store (https://your-instance.duckdns.org/hassio/store)

3- Install 'Eufy Security Add-on' 

4- When installation is completed, go to 'Configuration' page of Add-on and put Username (email), Password, Country (2 letter code), Event Duration in Seconds and Trusted Device Name.

5- Hit 'Start' and wait for it to be started.

6- Check 'Logs', you have to see something like this;
```
2022-12-27 20:09:16.339  INFO  Eufy Security server listening on host 0.0.0.0, port 3000 
2022-12-27 20:09:26.569  INFO  Connected to station T8010NXXX on host 87.240.219.ZZZ and port 29946 
2022-12-27 20:09:26.601  INFO  Connected to station T8410PXXX on host 87.240.219.YYY and port 18969 
```

## 2. Install RTSP Simple Server Add-on - Required for P2P Based Video Streaming - Not Required for RTSP Based Video Streaming ##
1- Add `RTSP Simple Server Add-on` Repository to `Add-On Store`. Please follow steps located here (https://www.home-assistant.io/common-tasks/os#installing-third-party-add-ons) and use this repository URL (https://github.com/fuatakgun/rtsp_simple_server/)

2- Search `RTSP Simple Server` on `Add-on Store` (https://your-instance.duckdns.org/hassio/store)

3- Install `RTSP Simple Server` 

4- Hit `Start` and wait for it to be started.

5- Check Logs, you have to see something like this;
```
2022/12/27 23:53:09 I [0/0] rtsp-simple-server v0.17.6
2022/12/27 23:53:09 I [0/0] [RTSP] TCP listener opened on :8554
2022/12/27 23:53:09 I [0/0] [RTMP] listener opened on :1935
2022/12/27 23:53:09 I [0/0] [HLS] listener opened on :8888
```

## 3. Installing Eufy Security Integration ##
1- If you have not already installed, install `HACS` following this guide: https://hacs.xyz/docs/setup/download

2- When `HACS` is ready, search for `Eufy Security` inside `HACS` Integrations

3- Install `Eufy Security` integration, restart your Home Assistant instance.

4- Check `Settings -> Devices & Services` page (https://your-instance.duckdns.org/config/integrations), click on `Add Integration` and search for `Eufy Security`. If you do not see it, first validate that it is installed via HACS and you had restarted it, later try with another browser. Integrations list might be already cached in your browser.

5- Put `Eufy Security Add-on IP Address` (127.0.0.1 for Supervised installation) and `configured port` (default 3000) and click Submit.

6- You might receive Captcha or Multi Factor Authentications (MFA) warnings, please Reconfigure the integration. Captcha code will be visible on Reconfigure page and MFA Code will be emailed or texted to you. Please enter these values. After this, you might need to restart your Home Assistant instance.

7- If you have installed `RTSP Simple Server Add-On`, please put its `IP Address` and `Port` into Integration Configuration page.

8- You can also configure `Cloud Scan Interval`, Video Analyze Duration, `Custom Name 1`, `Custom Name 2` and `Custom Name 3`

# Debugging Issues #
I am more than happy to debug individual issues as long as you follow setup instructions. I need you to share your problematic cameras with me so that I can use my own machine to debug the issue. For each debugging request, please create a github issue so we can track from there. Do not forget to remove the sharing settings after we are done :)

If you are located in EU, use my account: fuatakgun@gmail.com
If you are located in US, use shared test account: eufydeveloper@gmail.com
To schedule the time, please use this link: https://calendly.com/fuatakgun/office-hour