import boto3
from cdktf import App


class AwsApp(App):
    def synth(self):
        super().synth()

    # def set_context_defaults(self):
    #     context = self.node.get_all_context()
    #     if "CDKTF_CONTEXT_JSON" not in os.environ:
    #         config_file = Path("cdktf.json")
    #         if config_file.exists():
    #             with open("cdktf.json", "r") as fh:
    #                 config = json.load(fh)
    #                 context.update(config.get("context", {}))

    #     vpc = self.get_vpc(context.get("vpc_id", None))
    #     subnets = context.get("subnets", None)
    #     if not subnets:
    #         subnets = list(vpc.subnets.all())
    #         private_subnet_ids = [
    #             s.id for s in subnets if "private" in tags(s).get("Name", "").lower()
    #         ]

    #     context["vpc_id"] = context.get("vcd_id", vpc.id)
    #     context["subnets"] = context.get("subnets", private_subnet_ids)

    #     config["context"].update(context)

    #     with open("cdktf.json", "w") as fh:
    #         json.dump(config, fh, indent=2)

    def get_vpc(self, vpc_id=None):
        ec2 = boto3.resource("ec2")
        if vpc_id:
            return ec2.Vpc(vpc_id)
        return next((vpc for vpc in ec2.vpcs.all() if vpc.is_default), None)
