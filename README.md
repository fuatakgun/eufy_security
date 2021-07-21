I have baked a custom integration to control Eufy Security Cameras and access RSTP (real time streaming protocol) stream if possible. You can turn on and turn off cameras and if your camera is on, you can view live stream. Morevoer, there are some additional sensors for motion detection, person detection, battery level and wifi signal.

Installation;
Please follow screenshots below. In summary;
- You will first install HASS Add On assuming you are running on Hassos or Supervised. If not, please execute this command to run docker instance manually ```docker run -it -e USERNAME=email@address.com -e PASSWORD=password_goes_here -p 3000:3000 bropat/eufy-security-ws:latest```
- When you are done with HASS Add On, you will install integration via adding integration address to HACS, downloading files over UI, restarting home assistant and setting up integration.

![1-add-on-store](https://user-images.githubusercontent.com/11085566/126563889-8bc98e9a-8cb5-4f71-a3a7-3bde8e3f1182.PNG)

![2-add-on-repository](https://user-images.githubusercontent.com/11085566/126563898-8c642026-1e16-4484-8177-0bc6a93d59e8.PNG)

![3-add-on-visible](https://user-images.githubusercontent.com/11085566/126563911-ec5e0e52-312b-4e65-a25b-54a02a348752.PNG)

![4-add-on-configure](https://user-images.githubusercontent.com/11085566/126563919-273e413b-f2ac-49c4-8342-dfd5c5887ccf.PNG)

![5-add-on-log](https://user-images.githubusercontent.com/11085566/126563928-3ee2d48d-06e2-4681-9076-3992f4546b16.PNG)

![6-hacs-custom-repositories](https://user-images.githubusercontent.com/11085566/126563932-e9fc2783-02a1-42d3-8f4a-bc0fa2edf386.PNG)

![7-hacs-add](https://user-images.githubusercontent.com/11085566/126563937-4ad08d92-b9c1-45e3-a205-be9b244bc3a7.PNG)

![8-hacs-install](https://user-images.githubusercontent.com/11085566/126563950-1c89c1e8-f77d-46ac-8910-77048500a07f.PNG)

![9-hacs-restart](https://user-images.githubusercontent.com/11085566/126563954-b801e4ea-b93e-4695-928d-a82221fe01f4.PNG)

![10-integrations](https://user-images.githubusercontent.com/11085566/126563961-a05c5e50-b006-4759-b55a-548f691a13d8.PNG)

![11-integration-search](https://user-images.githubusercontent.com/11085566/126563968-920a74de-ab93-456b-b4b2-dcf651a07f9f.PNG)

![12-integration-configure](https://user-images.githubusercontent.com/11085566/126563976-234005e7-2920-4ef0-a301-187d4d929f10.png)

![13-integration-done](https://user-images.githubusercontent.com/11085566/126563982-38b3a00a-ff6a-45aa-8dcc-b04e864a37f8.PNG)

![14-services-live-stream](https://user-images.githubusercontent.com/11085566/126563991-5ef949c5-144c-4702-a9e3-577e2d37c0f8.PNG)




Raise your issues in Github. 

![Installation](https://github.com/fuatakgun/eufy_security/blob/master/eufy1.PNG?raw=true)

![Installation](https://github.com/fuatakgun/eufy_security/blob/master/eufy2.PNG?raw=true)

![Installation](https://github.com/fuatakgun/eufy_security/blob/master/eufy3.PNG?raw=true)

![Installation](https://github.com/fuatakgun/eufy_security/blob/master/eufy4.PNG?raw=true)

![Installation](https://github.com/fuatakgun/eufy_security/blob/master/eufy5.PNG?raw=true)

![Installation](https://github.com/fuatakgun/eufy_security/blob/master/stream.PNG?raw=true)

![Installation](https://github.com/fuatakgun/eufy_security/blob/master/motion%20detected.PNG?raw=true)
