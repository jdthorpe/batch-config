# setup

```ps1

# parameters
$name = "jathorpeszshnhnlzwvo"
$env:name = "jathorpeszshnhnlzwvo"
$location = "westus2"
$AZURE_CR_NAME = $name

# create the resources (~3 min)
az group create -l $location -n $name
az storage account create -n $name -l $location -g $name
az batch account create -l $location -n $name -g $name --storage-account $name
az acr create -n $AZURE_CR_NAME -l $location -g $name --sku Basic
az acr update -n $AZURE_CR_NAME --admin-enabled true

# login to the acr server
az acr login -n $AZURE_CR_NAME

$env:BATCH_ACCOUNT_NAME = $name
$env:BATCH_ACCOUNT_KEY =  (az batch account keys list -n $name -g $name --query primary) -replace '"',''
$env:BATCH_ACCOUNT_ENDPOINT =  (az batch account show -n $name -g $name --query accountEndpoint) -replace '"',''
$env:STORAGE_ACCOUNT_KEY = (az storage account keys list -n $name --query [0].value) -replace '"',''
$env:STORAGE_ACCOUNT_CONNECTION_STRING= (az storage account show-connection-string --name $name --query connectionString) -replace '"',''

# Export required parameters
$env:REGISTRY_SERVER = (az acr show -n $AZURE_CR_NAME --query loginServer) -replace '"',''
$env:REGISTRY_USERNAME = (az acr credential show -n $AZURE_CR_NAME --query username) -replace '"',''
$env:REGISTRY_PASSWORD = (az acr credential show -n $AZURE_CR_NAME --query passwords[0].value) -replace '"',''


# login to the acr server
az acr login -n $AZURE_CR_NAME

$env:image_name = "${env:REGISTRY_SERVER}/test:v4"

# build the image locally
docker build . -t $env:image_name

# push to our worker image to the registry
docker push $env:image_name

python controller.py


$env:BATCH_ACCOUNT_NAME
$env:BATCH_ACCOUNT_KEY
$env:BATCH_ACCOUNT_URL
$env:STORAGE_ACCOUNT_KEY
$env:STORAGE_ACCOUNT_CONNECTION_STRING
$AZURE_CR_NAME
$env:REGISTRY_SERVER
$env:REGISTRY_USERNAME
$env:REGISTRY_PASSWORD


```

