
APP_NAME := $(shell basename "$$(pwd)")
TMP_DIR := $(shell readlink -m ./build/tests)


compile:
	mkdir -p ./build/tests/
	python ../vdom2fs/make.py -ve vdom2fs.conf ./build/$(APP_NAME)_compiled
	python ../vdom2fs/build.py ./build/$(APP_NAME)_compiled ./build/$(APP_NAME)_compiled.xml


run13: compile
	$(eval USER_DATA := "$(TMP_DIR)/vdom13_userdata/")
	$(eval CONT_NAME := "vdom13$(APP_NAME)")
	$(eval IMG_NAME := "vdom13$(APP_NAME)")
	$(eval DOCKERFILE := "vdom2fs/dockerfile_13")
	$(eval APP_XML := "./build/$(APP_NAME)_compiled.xml")

	@mkdir -p "$(USER_DATA)"
	-docker stop $(CONT_NAME)
	-docker rm -f $(CONT_NAME)

	tar -c ../$(DOCKERFILE) ./build/*.xml | docker build -f $(DOCKERFILE)  --build-arg APP_NAME=$(APP_NAME) -t $(IMG_NAME) -
	
	set -x && \
		docker run -it -d --name $(CONT_NAME) -v "$(USER_DATA)":/var/vdom $(IMG_NAME) && \
		CONT_IP=$$(docker inspect -f '{{.NetworkSettings.IPAddress}}' $(CONT_NAME)) && \
		VDOM13="python ../vdom2fs/vdom13.py $${CONT_IP}" && \
		$${VDOM13} --wait 60 && \
		$${VDOM13} --update $(APP_XML) && \
		$${VDOM13} --install $(APP_XML) && \
		$${VDOM13} --list && \
		$${VDOM13} --select $(APP_NAME) && \
		docker logs $(CONT_NAME) && \
		echo "\n\nhttp://$${CONT_IP}/\n\n";
	
	-docker attach $(CONT_NAME)
	docker stop $(CONT_NAME)
	
	@echo Complete.


run20: compile
	$(eval USER_DATA := "$(TMP_DIR)/vdom20_userdata/")
	$(eval CONT_NAME := "vdom20$(APP_NAME)")
	$(eval IMG_NAME := "vdom20$(APP_NAME)")
	$(eval DOCKERFILE := "vdom2fs/dockerfile_20")

	@mkdir -p "$(USER_DATA)"
	-docker stop $(CONT_NAME)
	-docker rm -f $(CONT_NAME)
	
	tar -c ../$(DOCKERFILE) ./build/*.xml | docker build -f $(DOCKERFILE)  --build-arg APP_NAME=$(APP_NAME) -t $(IMG_NAME) -

	docker run -it -d --name $(CONT_NAME) -v "$(USER_DATA)":/var/vdom/ $(IMG_NAME)
	
	set -x && \
		docker logs $(CONT_NAME) && \
		CONT_IP=$$(docker inspect -f '{{.NetworkSettings.IPAddress}}' $(CONT_NAME)) && \
		echo "\n\nhttp://$${CONT_IP}/\n\n";
	
	-@docker attach --detach-keys "ctrl-c" $(CONT_NAME)
	docker stop $(CONT_NAME)

	@echo Complete.


clean:
	rm -rf ./build/*

