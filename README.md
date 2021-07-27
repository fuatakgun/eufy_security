I have baked a custom integration to control Eufy Security Cameras and access RSTP (real time streaming protocol) stream if possible. You can turn on and turn off cameras and if your camera is on, you can view live stream. Morevoer, there are some additional sensors for motion detection, person detection, battery level and wifi signal.

**Big thanks to @bropat who made this possible. Please consider buying a coffee for him over here: https://ko-fi.com/bropat**

# Known Bugs/Issues #
1- Having multiple p2p streaming at parallel causes issues - https://github.com/fuatakgun/eufy_security/issues/25
2- Lock is not supported yet - https://github.com/fuatakgun/eufy_security/issues/23
3- Motion sensor is not supported yet - https://github.com/fuatakgun/eufy_security/issues/22
4- Some hosts are freezing when p2p stream is enabled, downgrade video quality as workaround or get latest codebase to test changes. - https://github.com/fuatakgun/eufy_security/issues/20

# Installation

***Warning, there is an existing integration (https://github.com/nonsleepr/ha-eufy-security) and I have used the same internal name with this integration, unintentinally. You can not keep both integrations and trying to install might cause issues. You can backup old one if you want to test this, just rename `custom_components/eufy_security` into something else (eg `eufy_security_nonsleepr`)***

Please follow screenshots below. In summary;
- You will first install HASS Add On assuming you are running on Hassos or Supervised. If not, please execute this command to run docker instance manually ```docker run -it -e USERNAME=email@address.com -e PASSWORD=password_goes_here -p 3000:3000 bropat/eufy-security-ws:latest```
- When you are done with HASS Add On, you will install integration via adding integration address to HACS, downloading files over UI, restarting home assistant and setting up integration.

## Custom Add-On
1- Go to Add-On Store page and select `Repositories`

![1-add-on-store](https://user-images.githubusercontent.com/11085566/126563889-8bc98e9a-8cb5-4f71-a3a7-3bde8e3f1182.PNG)

2- Add custom repository URL 
```https://github.com/fuatakgun/eufy_security_addon```

![2-add-on-repository](https://user-images.githubusercontent.com/11085566/126563898-8c642026-1e16-4484-8177-0bc6a93d59e8.PNG)

3- Confirm that you can see `Eufy Security WS Addon`

![3-add-on-visible](https://user-images.githubusercontent.com/11085566/126563911-ec5e0e52-312b-4e65-a25b-54a02a348752.PNG)

4- Click on `Eufy Security WS Addon`, install add-on and switch to `Configuration` page, fill username, password and **country code (2 letter)**. I advise you to create a new account and share your cameras from main account to new account. Use that new account for home assistant purposes only.

![4-add-on-configure](https://user-images.githubusercontent.com/11085566/126563919-273e413b-f2ac-49c4-8342-dfd5c5887ccf.PNG)

5-Validate that you are connected checking logs page.

![5-add-on-log](https://user-images.githubusercontent.com/11085566/126563928-3ee2d48d-06e2-4681-9076-3992f4546b16.PNG)

## Custom Integration

6- Go to HACS and click on `Custom repositories`

![6-hacs-custom-repositories](https://user-images.githubusercontent.com/11085566/126563932-e9fc2783-02a1-42d3-8f4a-bc0fa2edf386.PNG)

7- Add custom integration repository URL 
```https://github.com/fuatakgun/eufy_security/```

![7-hacs-add](https://user-images.githubusercontent.com/11085566/126563937-4ad08d92-b9c1-45e3-a205-be9b244bc3a7.PNG)

8- Install the `Eufy Secucirty` repository

![8-hacs-install](https://user-images.githubusercontent.com/11085566/126563950-1c89c1e8-f77d-46ac-8910-77048500a07f.PNG)

9- You need to restart your HA instance to pick up new repository.

![9-hacs-restart](https://user-images.githubusercontent.com/11085566/126563954-b801e4ea-b93e-4695-928d-a82221fe01f4.PNG)

10- After restart, go to `Configuration` - `Integrations` page and click on `Add Integration`

![10-integrations](https://user-images.githubusercontent.com/11085566/126563961-a05c5e50-b006-4759-b55a-548f691a13d8.PNG)

11- Search for ```Eufy Security``` and click on it

![11-integration-search](https://user-images.githubusercontent.com/11085566/126563968-920a74de-ab93-456b-b4b2-dcf651a07f9f.PNG)

12- In next page, use ```localhost``` if you have used Add-on installation, otherwise put your Docker instance ip address and keep `3000` as port

![12-integration-configure](https://user-images.githubusercontent.com/11085566/126563976-234005e7-2920-4ef0-a301-187d4d929f10.png)

13- You will be shown devices connected to your account.

![13-integration-done](https://user-images.githubusercontent.com/11085566/126563982-38b3a00a-ff6a-45aa-8dcc-b04e864a37f8.PNG)

14- If your camera does not support live stream, you can use `Start Live Stream` and `Stop Live Stream` services. They require camera entities as input, you can use UI for this.

![14-services-live-stream](https://user-images.githubusercontent.com/11085566/126563991-5ef949c5-144c-4702-a9e3-577e2d37c0f8.PNG)

Raise your issues in Github. 


# Troubleshooting

1- Create a separate account for HA integration as that account will be logged out automatically from mobile app when HA integration logged in. Do not forget to share your cameras with your new account and enable notifications for them. This integration depends on push notifications to catch events.

2- If your HA instant crashes and your camera supports 2k video streaming, try to reduce quality, 2k video encoding might be hard for your hardware. With latest codebase, I have tried to reduce the load on HA instance for this. https://github.com/fuatakgun/eufy_security/issues/20#issuecomment-886757165

3- As of now, live stream is limited to 3 minutes and this is hard limit implemented by Eufy, so we do not have a solution in place. So, if you keep live stream running more than 3 minutes, it will be turned off by hardware but your home assistant will not be notified on this. So, next time you want to start live stream, you notice that nothing will be happening as we assume that it is already running. As a workaround, please call stop and start in order. https://github.com/fuatakgun/eufy_security/issues/10#issuecomment-886251442

4- I am more than happy to debug individual issues as long as you follow setup instructions. I need you to share your problematic cameras with my eufy account `fuatakgun@gmail.com` so that I can use my own machine to debug the issue. For each debugging request, please create a github issue so we can track from there. Do not forget to remove the sharing settings after we are done :)
